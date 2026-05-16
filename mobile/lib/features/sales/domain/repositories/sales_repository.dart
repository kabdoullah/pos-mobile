import '../entities/sale.dart';

/// Abstract repository for sales operations.
abstract class SalesRepository {
  /// Create and submit a new sale.
  Future<Sale> createSale({
    required String totalAmount, // FCFA as string
    required String vatAmount, // FCFA as string
    required PaymentMethod paymentMethod,
  });

  /// Get sale history, optionally paginated.
  Future<List<Sale>> getSales({String? cursor, int limit = 50});

  /// Get a single sale by ID.
  Future<Sale?> getSale(String id);
}
