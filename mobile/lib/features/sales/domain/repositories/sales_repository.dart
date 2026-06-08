import 'package:decimal/decimal.dart';

import '../entities/cart_item.dart';
import '../entities/sale.dart';

/// Aggregated totals for a single day — computed in SQL.
typedef DailyStats =
    ({int saleCount, Decimal totalAmount, Decimal cashTotal, Decimal mobileMoneyTotal});

/// Abstract repository for sales operations.
abstract class SalesRepository {
  /// Create and submit a new sale with items.
  Future<Sale> createSale({
    required List<CartItem> items,
    required Decimal totalAmount,
    required Decimal vatAmount,
    required PaymentMethod paymentMethod,
    Decimal? cashAmount,
    Decimal? mobileMoneyAmount,
  });

  /// Get sale history, optionally paginated.
  Future<List<Sale>> getSales({String? cursor, int limit = 50});

  /// Get a single sale by ID.
  Future<Sale?> getSale(String id);

  /// Returns all sales created today (local device timezone).
  Future<List<Sale>> getTodaySales();

  /// Returns aggregated totals for today computed in SQL (O(1) in SQLite).
  Future<DailyStats> getTodayStats();

  /// Returns all sales created on the given date (local device timezone).
  Future<List<Sale>> getSalesByDate(DateTime date);
}
