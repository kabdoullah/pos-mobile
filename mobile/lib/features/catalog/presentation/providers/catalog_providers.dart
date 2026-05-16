import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/product.dart';
import '../../domain/repositories/catalog_repository.dart';

part 'catalog_providers.g.dart';

// TODO: Implement CatalogRepository with drift/retrofit data layer
class _CatalogRepositoryImpl implements CatalogRepository {
  @override
  Future<List<Product>> getProducts({
    String? query,
    String? cursor,
    int limit = 50,
  }) async {
    // TODO: Query drift table or call API
    return [];
  }

  @override
  Future<Product> createProduct({
    required String name,
    required String unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    // TODO: Insert into drift DB and sync to API
    throw UnimplementedError();
  }

  @override
  Future<Product> updateProduct({
    required String id,
    String? name,
    String? unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    // TODO: Update drift DB and mark dirty for sync
    throw UnimplementedError();
  }

  @override
  Future<void> deleteProduct(String id) async {
    // TODO: Soft delete in drift DB
    throw UnimplementedError();
  }

  @override
  Future<Product?> getProduct(String id) async {
    // TODO: Query drift DB
    return null;
  }
}

/// Provides the catalog repository instance.
@riverpod
CatalogRepository catalogRepository(Ref ref) {
  return _CatalogRepositoryImpl();
}

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
