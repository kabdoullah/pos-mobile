import 'package:drift/drift.dart' as drift;
import 'package:riverpod_annotation/riverpod_annotation.dart';
import 'package:uuid/uuid.dart';

import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart' hide Sales;
import '../../domain/entities/sale.dart' as sale_entity;
import '../../domain/repositories/sales_repository.dart';
import '../../../sync/presentation/providers/sync_providers.dart';
import 'cart_provider.dart';

part 'sales_providers.g.dart';

class _SalesRepositoryImpl implements SalesRepository {
  _SalesRepositoryImpl({
    required AppDatabase db,
    required SyncQueueRepository queueRepository,
  }) : _db = db,
       _queueRepository = queueRepository;

  final AppDatabase _db;
  final SyncQueueRepository _queueRepository;

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
    await _db
        .into(_db.sales)
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
    // For now, just create the sale payload
    final salePayload = {
      'id': saleId,
      'items': <dynamic>[],
      'total_amount': totalAmount,
      'vat_amount': vatAmount,
      'payment_method': _paymentMethodToDtoString(paymentMethod),
      'created_at': now.toIso8601String(),
    };

    await _queueRepository.enqueueSale(
      saleId: saleId,
      salePayload: salePayload,
    );

    return sale_entity.Sale(
      id: saleId,
      receiptNumber: 0,
      totalAmount: totalAmount,
      vatAmount: vatAmount,
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
        await (_db.select(_db.sales)
              ..orderBy([
                (t) => drift.OrderingTerm(
                  expression: t.createdAt,
                  mode: drift.OrderingMode.desc,
                ),
              ])
              ..limit(limit))
            .get();

    return sales
        .map(
          (s) => sale_entity.Sale(
            id: s.id,
            receiptNumber: s.receiptNumber,
            totalAmount: s.totalAmount,
            vatAmount: s.vatAmount,
            paymentMethod: _parsePaymentMethod(s.paymentMethod),
            createdAt: s.createdAt,
          ),
        )
        .toList();
  }

  @override
  Future<sale_entity.Sale?> getSale(String id) async {
    final sale = await (_db.select(
      _db.sales,
    )..where((t) => t.id.equals(id))).getSingleOrNull();

    if (sale == null) return null;

    return sale_entity.Sale(
      id: sale.id,
      receiptNumber: sale.receiptNumber,
      totalAmount: sale.totalAmount,
      vatAmount: sale.vatAmount,
      paymentMethod: _parsePaymentMethod(sale.paymentMethod),
      createdAt: sale.createdAt,
    );
  }

  String _paymentMethodToString(sale_entity.PaymentMethod method) {
    return switch (method) {
      sale_entity.PaymentMethod.cash => 'cash',
      sale_entity.PaymentMethod.orangeMoney => 'orangeMoney',
      sale_entity.PaymentMethod.mtn => 'mtn',
      sale_entity.PaymentMethod.wave => 'wave',
      sale_entity.PaymentMethod.mixed => 'mixed',
    };
  }

  String _paymentMethodToDtoString(sale_entity.PaymentMethod method) {
    return switch (method) {
      sale_entity.PaymentMethod.cash => 'cash',
      sale_entity.PaymentMethod.orangeMoney => 'mobile_money_orange',
      sale_entity.PaymentMethod.mtn => 'mobile_money_mtn',
      sale_entity.PaymentMethod.wave => 'mobile_money_wave',
      sale_entity.PaymentMethod.mixed => 'mixed',
    };
  }

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
}

/// Provides the sales repository instance.
@riverpod
SalesRepository salesRepository(Ref ref) {
  final db = ref.watch(databaseProvider);
  final queueRepository = SyncQueueRepository(db: db);
  return _SalesRepositoryImpl(db: db, queueRepository: queueRepository);
}

/// Submit current cart as a sale.
@riverpod
Future<sale_entity.Sale> submitSale(
  Ref ref, {
  required String totalAmount,
  required String vatAmount,
  required sale_entity.PaymentMethod paymentMethod,
}) async {
  final repo = ref.watch(salesRepositoryProvider);

  final sale = await repo.createSale(
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: paymentMethod,
  );

  // Clear cart after successful submission
  ref.read(cartProvider.notifier).clear();

  return sale;
}

/// Loads sales for a specific date from local Drift DB.
@riverpod
Future<List<sale_entity.Sale>> salesHistory(
  Ref ref, {
  required DateTime date,
}) async {
  final repo = ref.watch(salesRepositoryProvider);
  final allSales = await repo.getSales(limit: 500);

  return allSales
      .where(
        (s) =>
            s.createdAt.year == date.year &&
            s.createdAt.month == date.month &&
            s.createdAt.day == date.day,
      )
      .toList();
}
