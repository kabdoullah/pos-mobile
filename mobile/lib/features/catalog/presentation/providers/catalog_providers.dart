import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../providers/catalog_di_providers.dart';
import '../../domain/entities/product.dart';

part 'catalog_providers.g.dart';

/// CatalogListNotifier manages product list with pagination and search.
@riverpod
class CatalogList extends _$CatalogList {
  String _searchQuery = '';
  String? _nextCursor;
  bool _hasMore = true;

  @override
  Future<List<Product>> build() async {
    final repo = ref.watch(catalogRepositoryProvider);
    return repo.getProducts();
  }

  /// Search products by name (debounced by caller).
  Future<void> search(String query) async {
    _searchQuery = query;
    _nextCursor = null;
    _hasMore = true;
    final repo = ref.read(catalogRepositoryProvider);
    state = await AsyncValue.guard(() => repo.getProducts(query: query));
  }

  /// Load next page of products.
  Future<void> loadMore() async {
    if (!_hasMore || state.isLoading) return;

    final repo = ref.read(catalogRepositoryProvider);
    final currentList = state.whenData((list) => list).value ?? [];

    state = await AsyncValue.guard(() async {
      final next = await repo.getProducts(
        query: _searchQuery.isEmpty ? null : _searchQuery,
        cursor: _nextCursor,
      );
      if (next.isEmpty) _hasMore = false;
      return [...currentList, ...next];
    });
  }

  /// Refresh product list (clear cursor, reload from start).
  Future<void> refresh() async {
    _nextCursor = null;
    _hasMore = true;
    final repo = ref.read(catalogRepositoryProvider);
    state = await AsyncValue.guard(
      () => repo.getProducts(query: _searchQuery.isEmpty ? null : _searchQuery),
    );
  }

  /// Create a new product.
  Future<void> createProduct({
    required String name,
    required String unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    final repo = ref.read(catalogRepositoryProvider);
    await repo.createProduct(
      name: name,
      unitPrice: unitPrice,
      barcode: barcode,
      currentStock: currentStock,
    );
    // Refresh list after creation
    await refresh();
  }

  /// Update an existing product.
  Future<void> updateProduct({
    required String id,
    String? name,
    String? unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    final repo = ref.read(catalogRepositoryProvider);
    await repo.updateProduct(
      id: id,
      name: name,
      unitPrice: unitPrice,
      barcode: barcode,
      currentStock: currentStock,
    );
    // Refresh list after update
    await refresh();
  }

  /// Delete a product by ID.
  Future<void> deleteProduct(String id) async {
    final repo = ref.read(catalogRepositoryProvider);
    await repo.deleteProduct(id);
    // Refresh list after deletion
    await refresh();
  }
}

/// Get a single product by ID for edit form.
@riverpod
Future<Product?> product(Ref ref, String id) async {
  final repo = ref.watch(catalogRepositoryProvider);
  return repo.getProduct(id);
}
