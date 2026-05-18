import 'package:decimal/decimal.dart';

import '../entities/cart_item.dart';
import '../entities/sale.dart';

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
}
