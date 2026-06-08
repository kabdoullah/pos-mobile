import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

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

/// Loads today's sales summary via a single SQL aggregation query (O(1)).
@riverpod
Future<DailySummary> dailySummary(Ref ref) async {
  final repo = ref.watch(salesRepositoryProvider);
  final stats = await repo.getTodayStats();

  return DailySummary(
    totalAmount: stats.totalAmount,
    saleCount: stats.saleCount,
    cashTotal: stats.cashTotal,
    mobileMoneyTotal: stats.mobileMoneyTotal,
  );
}
