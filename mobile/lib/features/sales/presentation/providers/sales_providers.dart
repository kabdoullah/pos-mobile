import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../providers/sales_di_providers.dart';
import '../../domain/entities/sale.dart' as sale_entity;
import 'cart_provider.dart';

part 'sales_providers.g.dart';

/// Submit current cart as a sale (calls CreateSaleUseCase).
@riverpod
Future<sale_entity.Sale> submitSale(
  Ref ref, {
  required Decimal totalAmount,
  required Decimal vatAmount,
  required sale_entity.PaymentMethod paymentMethod,
  Decimal? cashAmount,
  Decimal? mobileMoneyAmount,
}) async {
  final useCase = ref.read(createSaleUseCaseProvider);
  final cartState = ref.read(cartProvider);

  final sale = await useCase(
    items: cartState.items,
    totalAmount: totalAmount,
    vatAmount: vatAmount,
    paymentMethod: paymentMethod,
    cashAmount: cashAmount,
    mobileMoneyAmount: mobileMoneyAmount,
  );

  return sale;
}

/// Loads sales for a specific date from local Drift DB.
@riverpod
Future<List<sale_entity.Sale>> salesHistory(
  Ref ref, {
  required DateTime date,
}) async {
  return ref.read(salesRepositoryProvider).getSalesByDate(date);
}
