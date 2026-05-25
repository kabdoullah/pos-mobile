import 'product.dart';

/// Product page result with pagination metadata.
class ProductPage {
  /// Creates a ProductPage.
  const ProductPage({
    required this.items,
    required this.nextCursor,
    required this.hasMore,
  });

  /// List of products in this page.
  final List<Product> items;

  /// Cursor for fetching next page. Null if no more pages.
  final String? nextCursor;

  /// Whether more pages exist.
  final bool hasMore;
}
