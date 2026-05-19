import 'dart:convert';

import 'package:drift/drift.dart' as drift;

import '../../database/app_database.dart';

/// Repository for managing the sync queue (SyncQueue table).
class SyncQueueRepository {
  /// Constructor.
  SyncQueueRepository({required AppDatabase db}) : _db = db;

  final AppDatabase _db;

  static const int _maxRetries = 5;

  /// Enqueue a sale for synchronization.
  /// Returns the queue entry ID.
  Future<int> enqueueSale({
    required String saleId,
    required Map<String, dynamic> salePayload,
  }) async {
    final result = await _db
        .into(_db.syncQueue)
        .insert(
          SyncQueueCompanion(
            entityType: const drift.Value('sale'),
            entityId: drift.Value(saleId),
            payload: drift.Value(jsonEncode(salePayload)),
            status: const drift.Value('pending'),
            createdAt: drift.Value(DateTime.now()),
          ),
        );
    return result;
  }

  /// Enqueue a product change for synchronization.
  /// Returns the queue entry ID.
  Future<int> enqueueProductChange({
    required String productId,
    required Map<String, dynamic> productPayload,
  }) async {
    final result = await _db
        .into(_db.syncQueue)
        .insert(
          SyncQueueCompanion(
            entityType: const drift.Value('product'),
            entityId: drift.Value(productId),
            payload: drift.Value(jsonEncode(productPayload)),
            status: const drift.Value('pending'),
            createdAt: drift.Value(DateTime.now()),
          ),
        );
    return result;
  }

  /// Get pending or failed entries up to the specified limit.
  Future<List<SyncQueueData>> getPendingEntries({
    int limit = 50,
    List<String> entityTypes = const ['sale', 'product'],
  }) async {
    final entries =
        await (_db.select(_db.syncQueue)
              ..where((t) => t.status.isIn(['pending', 'failed']))
              ..where((t) => t.entityType.isIn(entityTypes))
              ..orderBy([(t) => drift.OrderingTerm(expression: t.createdAt)])
              ..limit(limit))
            .get();
    return entries;
  }

  /// Mark a queue entry as syncing.
  Future<bool> markSyncing(int id) async {
    final rowsAffected =
        await (_db.update(_db.syncQueue)..where((t) => t.id.equals(id))).write(
          SyncQueueCompanion(
            status: const drift.Value('syncing'),
            lastAttemptAt: drift.Value(DateTime.now()),
          ),
        );
    return rowsAffected > 0;
  }

  /// Mark a queue entry as successfully synced.
  Future<bool> markSynced(int id) async {
    final rowsAffected =
        await (_db.update(_db.syncQueue)..where((t) => t.id.equals(id))).write(
          SyncQueueCompanion(
            status: const drift.Value('synced'),
            lastAttemptAt: drift.Value(DateTime.now()),
          ),
        );
    return rowsAffected > 0;
  }

  /// Mark a queue entry as failed with an error message.
  Future<bool> markFailed(int id, String error) async {
    final rowsAffected =
        await (_db.update(_db.syncQueue)..where((t) => t.id.equals(id))).write(
          SyncQueueCompanion(
            status: const drift.Value('failed'),
            lastError: drift.Value(error),
            lastAttemptAt: drift.Value(DateTime.now()),
          ),
        );
    return rowsAffected > 0;
  }

  /// Increment the retry count for an entry.
  Future<bool> incrementRetry(int id) async {
    final entry = await (_db.select(
      _db.syncQueue,
    )..where((t) => t.id.equals(id))).getSingleOrNull();
    if (entry == null) return false;

    final newRetryCount = entry.retryCount + 1;
    final newStatus = newRetryCount > _maxRetries ? 'failed' : 'pending';

    final rowsAffected =
        await (_db.update(_db.syncQueue)..where((t) => t.id.equals(id))).write(
          SyncQueueCompanion(
            retryCount: drift.Value(newRetryCount),
            status: drift.Value(newStatus),
          ),
        );
    return rowsAffected > 0;
  }

  /// Purge synced entries older than 7 days.
  Future<int> purgeSynced() async {
    final sevenDaysAgo = DateTime.now().subtract(const Duration(days: 7));
    return (_db.delete(_db.syncQueue)..where(
          (t) =>
              t.status.equals('synced') &
              t.createdAt.isSmallerThanValue(sevenDaysAgo),
        ))
        .go();
  }

  /// Get a specific queue entry by ID.
  Future<SyncQueueData?> getEntry(int id) async {
    return (_db.select(
      _db.syncQueue,
    )..where((t) => t.id.equals(id))).getSingleOrNull();
  }

  /// Clear all entries (for testing).
  Future<int> clear() async {
    return (_db.delete(_db.syncQueue)).go();
  }

  /// Get all pending/failed entries by entity type.
  Future<List<SyncQueueData>> getEntriesByType(String entityType) async {
    return (_db.select(_db.syncQueue)
          ..where((t) => t.entityType.equals(entityType))
          ..where((t) => t.status.isIn(['pending', 'failed']))
          ..orderBy([(t) => drift.OrderingTerm(expression: t.createdAt)]))
        .get();
  }
}
