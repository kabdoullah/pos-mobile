import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/network_providers.dart';
import '../../../../core/sync/pull_service.dart';
import '../../../../core/sync/push_service.dart';
import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart';

part 'sync_providers.g.dart';

/// Provides the app database instance (singleton, never disposed).
@Riverpod(keepAlive: true)
AppDatabase database(Ref ref) {
  return AppDatabase();
}

/// Provides the pull service for syncing changes.
@riverpod
PullService pullService(Ref ref) {
  return PullService(
    remoteDataSource: ref.read(syncRemoteDataSourceProvider),
    db: ref.read(databaseProvider),
    logger: Logger(),
  );
}

/// Pulls changes from server and updates local drift.
@riverpod
Future<bool> pullChanges(Ref ref) async {
  final service = ref.read(pullServiceProvider);
  return service.pullChanges();
}

/// Provides the sync queue repository for managing pending syncs.
@riverpod
SyncQueueRepository syncQueueRepository(Ref ref) {
  return SyncQueueRepository(db: ref.read(databaseProvider));
}

/// Provides the push service for syncing local changes to server.
@riverpod
PushService pushService(Ref ref) {
  return PushService(
    remoteDataSource: ref.read(syncRemoteDataSourceProvider),
    queueRepository: ref.read(syncQueueRepositoryProvider),
    db: ref.read(databaseProvider),
    logger: Logger(),
  );
}

/// Live count of pending and failed sync queue entries.
@riverpod
Stream<int> pendingSyncCount(Ref ref) {
  final db = ref.watch(databaseProvider);
  return (db.select(db.syncQueue)
        ..where((row) => row.status.isIn(['pending', 'failed'])))
      .watch()
      .map((rows) => rows.length);
}
