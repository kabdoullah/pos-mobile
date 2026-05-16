import 'package:riverpod_annotation/riverpod_annotation.dart';

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
  final int totalAmount;

  /// Number of completed sales today.
  final int saleCount;

  /// Cash portion of total.
  final int cashTotal;

  /// Mobile money portion (all types combined).
  final int mobileMoneyTotal;

  /// Empty summary for loading/error states.
  static const empty = DailySummary(
    totalAmount: 0,
    saleCount: 0,
    cashTotal: 0,
    mobileMoneyTotal: 0,
  );
}

/// Loads daily summary from local Drift Sales table.
///
/// TODO: Query Drift DB: SELECT * FROM Sales WHERE date(createdAt) >= today_start
/// TODO: Group by paymentMethod and sum amounts
/// TODO: Implement after SalesRepository Drift data layer is complete
@riverpod
Future<DailySummary> dailySummary(Ref ref) async {
  return DailySummary.empty;
}
