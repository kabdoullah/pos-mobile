import 'package:decimal/decimal.dart';
import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart';
import '../../domain/entities/cart_item.dart';
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
    required List<CartItem> items,
    required Decimal totalAmount,
    required Decimal vatAmount,
    required sale_entity.PaymentMethod paymentMethod,
    Decimal? cashAmount,
    Decimal? mobileMoneyAmount,
  }) async {
    const uuid = Uuid();
    final saleId = uuid.v4();
    final now = DateTime.now().toUtc();

    // Build sync payload with items (before transaction)
    final itemPayloads = items
        .map(
          (item) => {
            'product_id': item.productId,
            'product_name_at_sale': item.productName,
            'unit_price_at_sale': item.unitPrice.toString(),
            'quantity': item.quantity,
            'line_total': item.lineTotal.toString(),
          },
        )
        .toList();

    final salePayload = {
      'id': saleId,
      'items': itemPayloads,
      'total_amount': totalAmount.toString(),
      'vat_amount': vatAmount.toString(),
      'payment_method': _paymentMethodToDtoString(paymentMethod),
      if (cashAmount != null) 'cash_amount': cashAmount.toString(),
      if (mobileMoneyAmount != null)
        'mobile_money_amount': mobileMoneyAmount.toString(),
      'created_at': now.toIso8601String(),
    };

    // Transaction: insert sale + items + queue entry atomically
    await db.transaction(() async {
      // Create sale record
      await db
          .into(db.sales)
          .insert(
            SalesCompanion(
              id: drift.Value(saleId),
              receiptNumber: const drift.Value(0),
              totalAmount: drift.Value(totalAmount.toString()),
              vatAmount: drift.Value(vatAmount.toString()),
              paymentMethod: drift.Value(_paymentMethodToString(paymentMethod)),
              createdAt: drift.Value(now),
            ),
          );

      // Create sale items
      for (final item in items) {
        final itemId = uuid.v4();
        await db
            .into(db.saleItems)
            .insert(
              SaleItemsCompanion(
                id: drift.Value(itemId),
                saleId: drift.Value(saleId),
                productId: drift.Value(item.productId),
                productName: drift.Value(item.productName),
                unitPrice: drift.Value(item.unitPrice.toString()),
                quantity: drift.Value(item.quantity),
                lineTotal: drift.Value(item.lineTotal.toString()),
              ),
            );
      }

      // Decrement stock for each item (products with null stock are unlimited)
      for (final item in items) {
        await db.customUpdate(
          'UPDATE products '
          'SET current_stock = current_stock - ?, dirty = 1 '
          'WHERE id = ? AND current_stock IS NOT NULL',
          variables: [
            drift.Variable.withInt(item.quantity),
            drift.Variable.withString(item.productId),
          ],
          updates: {db.products},
        );
      }

      // Enqueue for sync within same transaction (ensures atomicity)
      await syncQueue.enqueueSale(saleId: saleId, salePayload: salePayload);
    });

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
    final query = db.select(db.sales);
    // Keyset pagination: cursor is the createdAt ISO string of the last item.
    if (cursor != null) {
      final cursorDate = DateTime.parse(cursor);
      query.where((t) => t.createdAt.isSmallerThanValue(cursorDate));
    }
    query.orderBy([
      (t) => drift.OrderingTerm(
        expression: t.createdAt,
        mode: drift.OrderingMode.desc,
      ),
    ]);
    query.limit(limit);

    final sales = await query.get();
    return sales.map((s) => s.toDomain()).toList();
  }

  @override
  Future<List<sale_entity.Sale>> getSalesByDate(DateTime date) async {
    final dayStart = DateTime(date.year, date.month, date.day);
    final dayEnd = dayStart.add(const Duration(days: 1));

    final sales =
        await (db.select(db.sales)
              ..where(
                (t) =>
                    t.createdAt.isBiggerOrEqualValue(dayStart) &
                    t.createdAt.isSmallerThanValue(dayEnd),
              )
              ..orderBy([
                (t) => drift.OrderingTerm(
                  expression: t.createdAt,
                  mode: drift.OrderingMode.desc,
                ),
              ]))
            .get();

    return sales.map((s) => s.toDomain()).toList();
  }

  @override
  Stream<List<sale_entity.Sale>> watchSalesByDate(DateTime date) {
    final dayStart = DateTime(date.year, date.month, date.day);
    final dayEnd = dayStart.add(const Duration(days: 1));

    return (db.select(db.sales)
          ..where(
            (t) =>
                t.createdAt.isBiggerOrEqualValue(dayStart) &
                t.createdAt.isSmallerThanValue(dayEnd),
          )
          ..orderBy([
            (t) => drift.OrderingTerm(
              expression: t.createdAt,
              mode: drift.OrderingMode.desc,
            ),
          ]))
        .watch()
        .map((rows) => rows.map((s) => s.toDomain()).toList());
  }

  @override
  Future<sale_entity.Sale?> getSale(String id) async {
    final sale = await (db.select(
      db.sales,
    )..where((t) => t.id.equals(id))).getSingleOrNull();

    return sale?.toDomain();
  }

  @override
  Future<List<sale_entity.Sale>> getTodaySales() async {
    final now = DateTime.now();
    final todayStart = DateTime(now.year, now.month, now.day);

    final sales =
        await (db.select(db.sales)
              ..where((t) => t.createdAt.isBiggerOrEqualValue(todayStart))
              ..orderBy([
                (t) => drift.OrderingTerm(
                  expression: t.createdAt,
                  mode: drift.OrderingMode.desc,
                ),
              ]))
            .get();

    return sales.map((s) => s.toDomain()).toList();
  }

  @override
  Stream<DailyStats> watchTodayStats() {
    final now = DateTime.now();
    final todayStart = DateTime(now.year, now.month, now.day);

    return db
        .customSelect(
          'SELECT '
          '  COUNT(*) AS sale_count, '
          '  COALESCE(SUM(CAST(total_amount AS INTEGER)), 0) AS total, '
          '  COALESCE(SUM(CASE WHEN payment_method = ? THEN CAST(total_amount AS INTEGER) ELSE 0 END), 0) AS cash_total, '
          '  COALESCE(SUM(CASE WHEN payment_method != ? THEN CAST(total_amount AS INTEGER) ELSE 0 END), 0) AS mobile_total '
          'FROM sales WHERE created_at >= ?',
          variables: [
            drift.Variable.withString('cash'),
            drift.Variable.withString('cash'),
            drift.Variable.withDateTime(todayStart),
          ],
          readsFrom: {db.sales},
        )
        .watchSingle()
        .map((row) {
          Decimal fromInt(int v) => Decimal.fromInt(v);
          return (
            saleCount: row.read<int>('sale_count'),
            totalAmount: fromInt(row.read<int>('total')),
            cashTotal: fromInt(row.read<int>('cash_total')),
            mobileMoneyTotal: fromInt(row.read<int>('mobile_total')),
          );
        });
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
