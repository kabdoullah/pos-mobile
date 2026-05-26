import 'dart:convert';

import 'package:drift/drift.dart' as drift;
import 'package:logger/logger.dart';

import '../../core/network/api_models/product_dto.dart';
import '../../core/network/api_models/sale_dto.dart';
import '../../core/network/api_models/sync_changes_dto.dart';
import '../../core/network/api_models/sync_responses_dto.dart';
import '../../database/app_database.dart';
import '../../features/sync/data/datasources/sync_remote_datasource.dart';
import 'sync_queue_repository.dart';

/// Service for pushing local changes (sales, products) to the server.
class PushService {
  /// Constructor.
  PushService({
    required SyncRemoteDataSource remoteDataSource,
    required SyncQueueRepository queueRepository,
    required AppDatabase db,
    Logger? logger,
  }) : _remoteDataSource = remoteDataSource,
       _queueRepository = queueRepository,
       _db = db,
       _logger = logger;

  final SyncRemoteDataSource _remoteDataSource;
  final SyncQueueRepository _queueRepository;
  final AppDatabase _db;
  final Logger? _logger;

  /// Push all pending sales to the server.
  /// Best-effort batch sync with idempotence handling.
  Future<void> pushPendingSales() async {
    try {
      final entries = await _queueRepository.getEntriesByType('sale');
      if (entries.isEmpty) {
        _logger?.d('No pending sales to push');
        return;
      }

      // Process in batches of 50 (backend limit)
      const batchSize = 50;
      for (var i = 0; i < entries.length; i += batchSize) {
        final batch = entries.skip(i).take(batchSize).toList();
        await _pushSalesBatch(batch);
      }
    } catch (e, st) {
      _logger?.e('Push pending sales failed', error: e, stackTrace: st);
    }
  }

  /// Push a batch of sales.
  Future<void> _pushSalesBatch(List<SyncQueueData> entries) async {
    // Mark all as syncing in one batch DB operation
    await _queueRepository.markSyncingBatch(entries.map((e) => e.id).toList());

    try {
      // Build request
      final sales = <SaleCreateDto>[];
      final entryMap = <String, SyncQueueData>{};

      for (final entry in entries) {
        entryMap[entry.entityId] = entry;
        final payload = jsonDecode(entry.payload) as Map<String, dynamic>;
        sales.add(SaleCreateDto.fromJson(payload));
      }

      // Call backend
      final response = await _remoteDataSource.pushSales(
        SalesSyncBatchRequestDto(sales: sales),
      );

      // Process results
      for (final result in response.results) {
        final entry = entryMap[result.id];
        if (entry == null) continue;

        switch (result.status) {
          case 'created':
          case 'already_exists':
            // Both treated as success for idempotence
            await _queueRepository.markSynced(entry.id);
            if (result.status == 'already_exists') {
              _logger?.i('Sale ${result.id} already synced (idempotent)');
            }
            break;
          case 'failed':
            // Increment retry; if threshold exceeded, mark permanent failure
            await _queueRepository.incrementRetry(entry.id);
            final errorMsg = result.error ?? 'Unknown error';

            final retryEntry = await _queueRepository.getEntry(entry.id);
            if (retryEntry != null && retryEntry.retryCount >= 5) {
              _logger?.w(
                'Sale ${result.id} failed permanently after 5 retries: $errorMsg',
              );
              await _queueRepository.markFailed(entry.id, errorMsg);
            } else {
              _logger?.i('Sale ${result.id} failed (will retry): $errorMsg');
            }
            break;
          default:
            _logger?.w('Unknown sale sync result status: ${result.status}');
        }
      }
    } catch (e, st) {
      // Network error; mark entries back as pending for retry
      for (final entry in entries) {
        await _queueRepository.markFailed(entry.id, 'Network error: $e');
      }
      _logger?.e('Push sales batch failed', error: e, stackTrace: st);
    }
  }

  /// Push all pending product changes to the server.
  /// State-based sync with conflict resolution (server wins).
  Future<void> pushPendingProductChanges() async {
    try {
      final entries = await _queueRepository.getEntriesByType('product');
      if (entries.isEmpty) {
        _logger?.d('No pending product changes to push');
        return;
      }

      for (final entry in entries) {
        await _pushProductChange(entry);
      }
    } catch (e, st) {
      _logger?.e('Push pending products failed', error: e, stackTrace: st);
    }
  }

  /// Push a single product change.
  Future<void> _pushProductChange(SyncQueueData entry) async {
    await _queueRepository.markSyncing(entry.id);

    try {
      final payload = jsonDecode(entry.payload) as Map<String, dynamic>;
      ProductSyncItemDto productItem;
      try {
        productItem = ProductSyncItemDto.fromJson(payload);
      } catch (_) {
        // Legacy payload used camelCase keys — repair from current drift state.
        final product = await (_db.select(_db.products)
              ..where((p) => p.id.equals(entry.entityId)))
            .getSingleOrNull();
        if (product == null) {
          await _queueRepository.markFailed(entry.id, 'Legacy payload: product not found locally');
          return;
        }
        productItem = ProductSyncItemDto(
          id: product.id,
          name: product.name,
          barcode: product.barcode,
          unitPrice: product.unitPrice,
          currentStock: product.currentStock,
          clientUpdatedAt: product.updatedAt.toUtc().toIso8601String(),
          deleted: product.deletedAt != null,
        );
        _logger?.i('Product ${entry.entityId} payload repaired from drift');
      }

      final response = await _remoteDataSource.pushProduct(productItem);

      switch (response.status) {
        case 'created':
        case 'updated':
        case 'no_change':
        case 'deleted':
          // All non-conflict outcomes are treated as success
          await _queueRepository.markSynced(entry.id);
          _logger?.i(
            'Product ${entry.entityId} synced (status: ${response.status})',
          );
          break;
        case 'conflict':
          // Server version is newer; overwrite local with server_state
          if (response.serverState != null) {
            await _updateProductFromServerState(response.serverState!);
            _logger?.i(
              'Product ${entry.entityId} conflict resolved (server won)',
            );
          }
          await _queueRepository.markSynced(entry.id);
          break;
        default:
          _logger?.w(
            'Unknown product sync response status: ${response.status}',
          );
      }
    } catch (e) {
      // Increment retry
      await _queueRepository.incrementRetry(entry.id);

      final retryEntry = await _queueRepository.getEntry(entry.id);
      if (retryEntry != null && retryEntry.retryCount >= 5) {
        _logger?.w(
          'Product ${entry.entityId} failed permanently after 5 retries',
        );
        await _queueRepository.markFailed(entry.id, 'Max retries exceeded: $e');
      } else {
        _logger?.i('Product ${entry.entityId} push failed (will retry): $e');
      }
    }
  }

  /// Update a local product from server state (used in conflict resolution).
  Future<void> _updateProductFromServerState(ProductDto serverState) async {
    final deletedAt = serverState.deletedAt != null
        ? DateTime.parse(serverState.deletedAt!)
        : null;

    await _db
        .update(_db.products)
        .replace(
          ProductsCompanion(
            id: drift.Value(serverState.id),
            name: drift.Value(serverState.name),
            barcode: drift.Value(serverState.barcode),
            unitPrice: drift.Value(serverState.unitPrice),
            currentStock: drift.Value(serverState.currentStock),
            dirty: const drift.Value(false), // Mark clean after sync
            updatedAt: drift.Value(DateTime.parse(serverState.updatedAt)),
            deletedAt: drift.Value(deletedAt),
          ),
        );
  }
}
