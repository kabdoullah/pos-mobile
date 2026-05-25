import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../sales/domain/entities/sale.dart';
import '../../../sales/providers/sales_di_providers.dart';

part 'home_providers.g.dart';

/// Summarizes today's sales totals by payment method.
class DailySummary {
  /// Creates a [DailySummary].
  const DailySummary({
    required this.totalAmount,
    required this.saleCount,
    required this.cashTotal,
    required this.mobileMoneyTotal,
  });

  /// Total revenue today in FCFA.
  final Decimal totalAmount;

  /// Number of completed sales today.
  final int saleCount;

  /// Cash portion of total.
  final Decimal cashTotal;

  /// Mobile money portion (all non-cash types combined).
  final Decimal mobileMoneyTotal;

  /// Empty summary for loading/error states.
  static final empty = DailySummary(
    totalAmount: Decimal.zero,
    saleCount: 0,
    cashTotal: Decimal.zero,
    mobileMoneyTotal: Decimal.zero,
  );
}

/// Loads daily summary from local Drift Sales table.
@riverpod
Future<DailySummary> dailySummary(Ref ref) async {
  final repo = ref.watch(salesRepositoryProvider);
  final sales = await repo.getTodaySales();

  var total = Decimal.zero;
  var cash = Decimal.zero;
  var mobileMoney = Decimal.zero;

  for (final sale in sales) {
    total += sale.totalAmount;
    if (sale.paymentMethod == PaymentMethod.cash) {
      cash += sale.totalAmount;
    } else {
      mobileMoney += sale.totalAmount;
    }
  }

  return DailySummary(
    totalAmount: total,
    saleCount: sales.length,
    cashTotal: cash,
    mobileMoneyTotal: mobileMoney,
  );
}
