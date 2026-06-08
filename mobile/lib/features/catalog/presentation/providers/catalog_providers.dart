import 'dart:async';

import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../../core/sync/sync_orchestrator.dart';
import '../../providers/catalog_di_providers.dart';
import '../../domain/entities/product.dart';

part 'catalog_providers.g.dart';

/// CatalogListNotifier manages product list with pagination and search.
@riverpod
class CatalogList extends _$CatalogList {
  String _searchQuery = '';
  String? _nextCursor;
  bool _hasMore = true;
  int _lastLoadMoreListLength = 0;
  Timer? _debounceTimer;

  @override
  Future<List<Product>> build() async {
    ref.onDispose(() => _debounceTimer?.cancel());

    // Refresh catalog when a sync cycle completes.
    ref.listen<SyncStatus>(syncOrchestratorProvider, (prev, next) {
      if (next is SyncStatusIdle) {
        ref.invalidateSelf();
      }
    });

    final repo = ref.watch(catalogRepositoryProvider);
    final page = await repo.getProducts();
    _nextCursor = page.nextCursor;
    _hasMore = page.hasMore;
    return page.items;
  }

  /// Debounced search entry-point called from the UI.
  void setSearchQuery(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(
      const Duration(milliseconds: 300),
      () => search(query),
    );
  }

  /// Search products by name.
  Future<void> search(String query) async {
    _searchQuery = query;
    _nextCursor = null;
    _hasMore = true;
    _lastLoadMoreListLength = 0;
    final repo = ref.read(catalogRepositoryProvider);
    final page = await repo.getProducts(query: query);
    _nextCursor = page.nextCursor;
    _hasMore = page.hasMore;
    state = AsyncData(page.items);
  }

  /// Load next page of products.
  /// Prevents duplicate requests via threshold tracking - only triggers once per new list size.
  Future<void> loadMore() async {
    if (!_hasMore || state.isLoading) return;

    final currentList = state.whenData((list) => list).value ?? [];

    // Only trigger loadMore once per list size increment
    if (currentList.length <= _lastLoadMoreListLength) return;
    _lastLoadMoreListLength = currentList.length;

    final repo = ref.read(catalogRepositoryProvider);

    state = await AsyncValue.guard(() async {
      final page = await repo.getProducts(
        query: _searchQuery.isEmpty ? null : _searchQuery,
        cursor: _nextCursor,
      );
      _nextCursor = page.nextCursor;
      _hasMore = page.hasMore;
      return [...currentList, ...page.items];
    });
  }

  /// Refresh product list (clear cursor, reload from start).
  Future<void> refresh() async {
    _nextCursor = null;
    _hasMore = true;
    _lastLoadMoreListLength = 0;
    final repo = ref.read(catalogRepositoryProvider);
    state = await AsyncValue.guard(() async {
      final page = await repo.getProducts(
        query: _searchQuery.isEmpty ? null : _searchQuery,
      );
      _nextCursor = page.nextCursor;
      _hasMore = page.hasMore;
      return page.items;
    });
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
