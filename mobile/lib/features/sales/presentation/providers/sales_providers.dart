import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/repository_providers.dart';
import '../../domain/entities/sale.dart' as sale_entity;
import 'cart_provider.dart';

part 'sales_providers.g.dart';

/// Submit current cart as a sale.
@riverpod
Future<sale_entity.Sale> submitSale(
  Ref ref, {
  required Decimal totalAmount,
  required Decimal vatAmount,
  required sale_entity.PaymentMethod paymentMethod,
  Decimal? cashAmount,
  Decimal? mobileMoneyAmount,
}) async {
  final repo = ref.watch(salesRepositoryProvider);
  final cartState = ref.watch(cartProvider);

  final sale = await repo.createSale(
    items: cartState.items,
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: paymentMethod,
    cashAmount: cashAmount,
    mobileMoneyAmount: mobileMoneyAmount,
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
