import 'package:drift/drift.dart' as drift;
import 'package:logger/logger.dart';

import '../../database/app_database.dart';
import '../../features/sync/data/datasources/sync_remote_datasource.dart';
import '../utils/barcode_utils.dart';

/// Service for pulling changes from server and writing to local drift database.
class PullService {
  /// Constructor.
  const PullService({
    required SyncRemoteDataSource remoteDataSource,
    required AppDatabase db,
    Logger? logger,
  }) : _remoteDataSource = remoteDataSource,
       _db = db,
       _logger = logger;

  final SyncRemoteDataSource _remoteDataSource;
  final AppDatabase _db;
  final Logger? _logger;

  static const int _defaultLimit = 100;

  /// Pulls all changes from server and writes to drift (idempotent).
  ///
  /// Returns true if pull succeeded, false otherwise.
  /// On success, updates last_pull_at metadata.
  ///
  /// When [forceFullPull] is true, ignores [last_pull_at] and fetches the
  /// full catalog (since=null). Use for manual refresh to recover from
  /// products inserted on the server with timestamps older than last_pull_at.
  Future<bool> pullChanges({bool forceFullPull = false}) async {
    try {
      final storage = SyncMetadataStorage(_db);
      final lastPullAt = forceFullPull ? null : await storage.getLastPullAt();
      final since = lastPullAt?.toIso8601String();

      _logger?.d('Starting pull. Full: $forceFullPull. Last pull: $lastPullAt');

      String? cursor;
      bool hasMore = true;
      String? serverTime;

      // Paginate through all results.
      while (hasMore) {
        _logger?.d('Fetching page. Cursor: $cursor');

        final response = await _remoteDataSource.getChanges(
          since: since,
          limit: _defaultLimit,
          cursor: cursor,
        );

        serverTime = response.serverTime;

        // Upsert products (idempotent) — single batch transaction.
        if (response.products.isNotEmpty) {
          await _db.batch((batch) {
            for (final productDto in response.products) {
              final deletedAt = productDto.deletedAt != null
                  ? DateTime.parse(productDto.deletedAt!)
                  : null;
              batch.insert(
                _db.products,
                ProductsCompanion(
                  id: drift.Value(productDto.id),
                  name: drift.Value(productDto.name),
                  barcode: drift.Value(normalizeBarcode(productDto.barcode)),
                  unitPrice: drift.Value(productDto.unitPrice),
                  currentStock: drift.Value(productDto.currentStock),
                  dirty: const drift.Value(false),
                  updatedAt: drift.Value(DateTime.parse(productDto.updatedAt)),
                  deletedAt: drift.Value(deletedAt),
                ),
                mode: drift.InsertMode.insertOrReplace,
              );
            }
          });
        }

        // Upsert sales (idempotent, append-only) — single batch transaction.
        if (response.sales.isNotEmpty) {
          await _db.batch((batch) {
            for (final saleDto in response.sales) {
              batch.insert(
                _db.sales,
                SalesCompanion(
                  id: drift.Value(saleDto.id),
                  receiptNumber: drift.Value(saleDto.receiptNumber ?? 0),
                  totalAmount: drift.Value(saleDto.totalAmount),
                  vatAmount: drift.Value(saleDto.vatAmount),
                  paymentMethod: drift.Value(saleDto.paymentMethod),
                  createdAt: drift.Value(DateTime.parse(saleDto.createdAt)),
                ),
                mode: drift.InsertMode.insertOrReplace,
              );
            }
          });
        }

        // Pagination check.
        hasMore = response.hasMore;
        cursor = response.nextCursor;
      }

      // Update metadata only if pull completed successfully.
      if (serverTime != null) {
        final timestamp = DateTime.parse(serverTime);
        await storage.setLastPullAt(timestamp);
        _logger?.d('Pull completed. Server time: $serverTime');
      }

      return true;
    } catch (e, st) {
      _logger?.e('Pull failed', error: e, stackTrace: st);
      return false;
    }
  }
}

/// Manages sync metadata (last pull timestamp) stored in drift.
class SyncMetadataStorage {
  /// Constructor.
  const SyncMetadataStorage(this._db);

  final AppDatabase _db;

  /// Key for storing last pull timestamp.
  static const String _lastPullKey = 'last_pull_at';

  /// Reads last pull timestamp. Returns null if never pulled.
  Future<DateTime?> getLastPullAt() async {
    final record = await (_db.select(
      _db.syncMetadata,
    )..where((t) => t.key.equals(_lastPullKey))).getSingleOrNull();

    if (record == null) return null;
    return DateTime.parse(record.value);
  }

  /// Stores last pull timestamp (server_time from sync response).
  Future<void> setLastPullAt(DateTime timestamp) async {
    await _db
        .into(_db.syncMetadata)
        .insertOnConflictUpdate(
          SyncMetadataCompanion(
            key: const drift.Value(_lastPullKey),
            value: drift.Value(timestamp.toIso8601String()),
            updatedAt: drift.Value(DateTime.now()),
          ),
        );
  }

  /// Clears all sync metadata (used in tests or reset scenarios).
  Future<void> clear() async {
    await (_db.delete(_db.syncMetadata)).go();
  }
}
