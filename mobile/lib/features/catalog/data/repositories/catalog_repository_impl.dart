import 'package:decimal/decimal.dart';
import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../../../../core/sync/sync_queue_repository.dart';
import '../../../../database/app_database.dart' hide Product;
import '../../domain/entities/product.dart' as product_domain;
import '../../domain/entities/product_page.dart';
import '../../domain/repositories/catalog_repository.dart';
import '../models/product_mappers.dart';

/// Concrete implementation of [CatalogRepository].
/// Local-first: reads/writes drift database. Changes enqueued for sync.
class CatalogRepositoryImpl implements CatalogRepository {
  /// Creates a CatalogRepositoryImpl.
  CatalogRepositoryImpl({required this.db, required this.syncQueue});

  /// Local drift database instance.
  final AppDatabase db;

  /// Sync queue repository for marking changes.
  final SyncQueueRepository syncQueue;

  @override
  Future<ProductPage> getProducts({
    String? query,
    String? cursor,
    int limit = 50,
  }) async {
    final dbQuery = db.select(db.products);

    // Filter deleted
    dbQuery.where((p) => p.deletedAt.isNull());

    // Search by name or barcode
    if (query != null && query.isNotEmpty) {
      final searchTerm = '%$query%';
      dbQuery.where(
        (p) => p.name.like(searchTerm) | p.barcode.like(searchTerm),
      );
    }

    dbQuery.orderBy([(p) => drift.OrderingTerm(expression: p.id)]);

    final records = await dbQuery.get();

    // Client-side pagination: skip to cursor, then take limit
    final startIndex = cursor == null
        ? 0
        : records.indexWhere((r) => r.id == cursor) + 1;
    if (startIndex < 0) {
      return const ProductPage(items: [], nextCursor: null, hasMore: false);
    }

    final remaining = records.skip(startIndex).toList();
    final items = remaining.take(limit).map((r) => r.toDomain()).toList();

    // Calculate next cursor and has_more
    final nextCursor = items.isNotEmpty && remaining.length > limit
        ? items.last.id
        : null;
    final hasMore = remaining.length > limit;

    return ProductPage(items: items, nextCursor: nextCursor, hasMore: hasMore);
  }

  @override
  Future<product_domain.Product> createProduct({
    required String name,
    required String unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    final id = const Uuid().v4();
    final now = DateTime.now();
    final product = product_domain.Product(
      id: id,
      name: name,
      unitPrice: Decimal.parse(unitPrice),
      barcode: barcode,
      currentStock: currentStock,
      updatedAt: now,
      deletedAt: null,
    );

    // Write to drift
    await db
        .into(db.products)
        .insert(
          ProductsCompanion(
            id: drift.Value(id),
            name: drift.Value(name),
            barcode: barcode != null
                ? drift.Value(barcode)
                : const drift.Value.absent(),
            unitPrice: drift.Value(unitPrice),
            currentStock: currentStock != null
                ? drift.Value(currentStock)
                : const drift.Value.absent(),
            dirty: const drift.Value(true), // Mark for sync
            updatedAt: drift.Value(now),
          ),
        );

    // Enqueue for synchronization
    await syncQueue.enqueueProductChange(
      productId: id,
      productPayload: {
        'id': id,
        'name': name,
        'barcode': barcode,
        'unitPrice': unitPrice,
        'currentStock': currentStock,
      },
    );

    return product;
  }

  @override
  Future<product_domain.Product> updateProduct({
    required String id,
    String? name,
    String? unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    // Fetch current product
    final current = await (db.select(
      db.products,
    )..where((p) => p.id.equals(id))).getSingleOrNull();
    if (current == null) {
      throw Exception('Product not found: $id');
    }

    final now = DateTime.now();
    final updatedName = name ?? current.name;
    final updatedPrice = unitPrice ?? current.unitPrice;
    final updatedBarcode = barcode ?? current.barcode;
    final updatedStock = currentStock ?? current.currentStock;

    // Update drift
    await (db.update(db.products)..where((p) => p.id.equals(id))).write(
      ProductsCompanion(
        name: drift.Value(updatedName),
        barcode: updatedBarcode != null
            ? drift.Value(updatedBarcode)
            : const drift.Value.absent(),
        unitPrice: drift.Value(updatedPrice),
        currentStock: updatedStock != null
            ? drift.Value(updatedStock)
            : const drift.Value.absent(),
        dirty: const drift.Value(true), // Mark for sync
        updatedAt: drift.Value(now),
      ),
    );

    // Enqueue for synchronization
    await syncQueue.enqueueProductChange(
      productId: id,
      productPayload: {
        'id': id,
        'name': updatedName,
        'barcode': updatedBarcode,
        'unitPrice': updatedPrice,
        'currentStock': updatedStock,
      },
    );

    return product_domain.Product(
      id: id,
      name: updatedName,
      unitPrice: Decimal.parse(updatedPrice),
      barcode: updatedBarcode,
      currentStock: updatedStock,
      updatedAt: now,
      deletedAt: null,
    );
  }

  @override
  Future<void> deleteProduct(String id) async {
    final now = DateTime.now();

    // Soft delete in drift
    await (db.update(db.products)..where((p) => p.id.equals(id))).write(
      ProductsCompanion(
        dirty: const drift.Value(true),
        deletedAt: drift.Value(now),
      ),
    );

    // Enqueue for synchronization
    await syncQueue.enqueueProductChange(
      productId: id,
      productPayload: {'id': id, 'deletedAt': now.toIso8601String()},
    );
  }

  @override
  Future<product_domain.Product?> getProduct(String id) async {
    final record =
        await (db.select(db.products)
              ..where((p) => p.id.equals(id))
              ..where((p) => p.deletedAt.isNull()))
            .getSingleOrNull();
    return record?.toDomain();
  }

  @override
  Future<product_domain.Product?> getByBarcode(String barcode) async {
    final record =
        await (db.select(db.products)
              ..where((p) => p.barcode.equals(barcode))
              ..where((p) => p.deletedAt.isNull()))
            .getSingleOrNull();
    return record?.toDomain();
  }
}
