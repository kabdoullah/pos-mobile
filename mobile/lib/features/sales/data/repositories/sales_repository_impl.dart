import 'package:decimal/decimal.dart';
import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart';
import '../../domain/entities/sale.dart' as sale_entity;
import '../../domain/repositories/sales_repository.dart';
import '../models/sale_mappers.dart';

/// Concrete implementation of [SalesRepository].
/// Local-first: reads/writes drift database. Changes enqueued for sync.
class SalesRepositoryImpl implements SalesRepository {
  /// Creates a SalesRepositoryImpl.
  SalesRepositoryImpl({required this.db, required this.syncQueue});

  /// Local drift database instance.
  final AppDatabase db;

  /// Sync queue repository for marking changes.
  final SyncQueueRepository syncQueue;

  @override
  Future<sale_entity.Sale> createSale({
    required String totalAmount,
    required String vatAmount,
    required sale_entity.PaymentMethod paymentMethod,
  }) async {
    const uuid = Uuid();
    final saleId = uuid.v4();
    final now = DateTime.now();

    // Create sale record in drift (receipt_number=0 until backend assigns one)
    await db
        .into(db.sales)
        .insert(
          SalesCompanion(
            id: drift.Value(saleId),
            receiptNumber: const drift.Value(0),
            totalAmount: drift.Value(totalAmount),
            vatAmount: drift.Value(vatAmount),
            paymentMethod: drift.Value(_paymentMethodToString(paymentMethod)),
            createdAt: drift.Value(now),
          ),
        );

    // Enqueue for sync (items will be added by caller if needed)
    final salePayload = {
      'id': saleId,
      'items': <dynamic>[],
      'total_amount': totalAmount,
      'vat_amount': vatAmount,
      'payment_method': _paymentMethodToDtoString(paymentMethod),
      'created_at': now.toIso8601String(),
    };

    await syncQueue.enqueueSale(saleId: saleId, salePayload: salePayload);

    return sale_entity.Sale(
      id: saleId,
      receiptNumber: 0,
      totalAmount: Decimal.parse(totalAmount),
      vatAmount: Decimal.parse(vatAmount),
      paymentMethod: paymentMethod,
      createdAt: now,
    );
  }

  @override
  Future<List<sale_entity.Sale>> getSales({
    String? cursor,
    int limit = 50,
  }) async {
    final sales =
        await (db.select(db.sales)
              ..orderBy([
                (t) => drift.OrderingTerm(
                  expression: t.createdAt,
                  mode: drift.OrderingMode.desc,
                ),
              ])
              ..limit(limit))
            .get();

    return sales.map((s) => s.toDomain()).toList();
  }

  @override
  Future<sale_entity.Sale?> getSale(String id) async {
    final sale = await (db.select(
      db.sales,
    )..where((t) => t.id.equals(id))).getSingleOrNull();

    return sale?.toDomain();
  }

  /// Converts domain PaymentMethod to drift string format.
  String _paymentMethodToString(sale_entity.PaymentMethod method) {
    return switch (method) {
      sale_entity.PaymentMethod.cash => 'cash',
      sale_entity.PaymentMethod.orangeMoney => 'orangeMoney',
      sale_entity.PaymentMethod.mtn => 'mtn',
      sale_entity.PaymentMethod.wave => 'wave',
      sale_entity.PaymentMethod.mixed => 'mixed',
    };
  }

  /// Converts domain PaymentMethod to API format string.
  String _paymentMethodToDtoString(sale_entity.PaymentMethod method) {
    return switch (method) {
      sale_entity.PaymentMethod.cash => 'cash',
      sale_entity.PaymentMethod.orangeMoney => 'mobile_money_orange',
      sale_entity.PaymentMethod.mtn => 'mobile_money_mtn',
      sale_entity.PaymentMethod.wave => 'mobile_money_wave',
      sale_entity.PaymentMethod.mixed => 'mixed',
    };
  }
}
