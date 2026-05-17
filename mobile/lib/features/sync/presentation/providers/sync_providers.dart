import 'package:logger/logger.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/network/network_providers.dart';
import '../../../../core/sync/pull_service.dart';
import '../../../../core/sync/push_service.dart';
import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart';
import '../../../catalog/domain/entities/product.dart' as product_entity;
import '../../../sales/domain/entities/sale.dart' as sale_entity;

part 'sync_providers.g.dart';

/// Provides the app database instance.
@riverpod
AppDatabase database(Ref ref) {
  return AppDatabase();
}

/// Provides the pull service for syncing changes.
@riverpod
PullService pullService(Ref ref) {
  final remoteDataSource = ref.watch(syncRemoteDataSourceProvider);
  final db = ref.watch(databaseProvider);

  return PullService(
    remoteDataSource: remoteDataSource,
    db: db,
    logger: Logger(),
  );
}

/// Watches products from local drift database and auto-updates.
@riverpod
Stream<List<product_entity.Product>> productsStream(Ref ref) async* {
  final db = ref.watch(databaseProvider);

  yield* db.select(db.products).watch().map((records) {
    return records
        .where((r) => r.deletedAt == null)
        .map(
          (r) => product_entity.Product(
            id: r.id,
            name: r.name,
            barcode: r.barcode,
            unitPrice: r.unitPrice,
            currentStock: r.currentStock,
            updatedAt: r.updatedAt,
            deletedAt: r.deletedAt,
          ),
        )
        .toList();
  });
}

/// Watches sales from local drift database and auto-updates.
@riverpod
Stream<List<sale_entity.Sale>> salesStream(Ref ref) async* {
  final db = ref.watch(databaseProvider);

  yield* db.select(db.sales).watch().map((records) {
    return records
        .map(
          (r) => sale_entity.Sale(
            id: r.id,
            receiptNumber: r.receiptNumber,
            totalAmount: r.totalAmount,
            vatAmount: r.vatAmount,
            paymentMethod: _parsePaymentMethod(r.paymentMethod),
            createdAt: r.createdAt,
          ),
        )
        .toList();
  });
}

/// Converts string payment method from DB to enum.
sale_entity.PaymentMethod _parsePaymentMethod(String method) {
  return switch (method) {
    'cash' => sale_entity.PaymentMethod.cash,
    'orangeMoney' => sale_entity.PaymentMethod.orangeMoney,
    'mtn' => sale_entity.PaymentMethod.mtn,
    'wave' => sale_entity.PaymentMethod.wave,
    'mixed' => sale_entity.PaymentMethod.mixed,
    _ => sale_entity.PaymentMethod.cash,
  };
}

/// Pulls changes from server and updates local drift.
@riverpod
Future<bool> pullChanges(Ref ref) async {
  final service = ref.watch(pullServiceProvider);
  final result = await service.pullChanges();

  if (result) {
    // Invalidate streams to trigger refresh
    ref.invalidate(productsStreamProvider);
    ref.invalidate(salesStreamProvider);
  }

  return result;
}

/// Provides the sync queue repository for managing pending syncs.
@riverpod
SyncQueueRepository syncQueueRepository(Ref ref) {
  return SyncQueueRepository(db: ref.watch(databaseProvider));
}

/// Provides the push service for syncing local changes to server.
@riverpod
PushService pushService(Ref ref) {
  return PushService(
    remoteDataSource: ref.watch(syncRemoteDataSourceProvider),
    queueRepository: ref.watch(syncQueueRepositoryProvider),
    db: ref.watch(databaseProvider),
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
