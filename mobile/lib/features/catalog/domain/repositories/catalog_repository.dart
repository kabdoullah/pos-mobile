import '../entities/product.dart';
import '../entities/product_page.dart';

/// Abstract repository for catalog operations.
abstract class CatalogRepository {
  /// Get products, optionally filtered by search query and paginated by cursor.
  /// Returns a page with pagination metadata.
  Future<ProductPage> getProducts({
    String? query,
    String? cursor,
    int limit = 50,
  });

  /// Create a new product.
  Future<Product> createProduct({
    required String name,
    required String unitPrice,
    String? barcode,
    int? currentStock,
  });

  /// Update an existing product.
  Future<Product> updateProduct({
    required String id,
    String? name,
    String? unitPrice,
    String? barcode,
    int? currentStock,
  });

  /// Delete (soft delete) a product by ID.
  Future<void> deleteProduct(String id);

  /// Get a single product by ID.
  Future<Product?> getProduct(String id);

  /// Find a product by barcode. Returns null if not found.
  Future<Product?> getByBarcode(String barcode);
}
