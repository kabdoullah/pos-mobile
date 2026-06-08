import 'package:decimal/decimal.dart';
import 'package:drift/drift.dart' as drift;
import 'package:uuid/uuid.dart';

import '../../../../core/network/api_models/sync_changes_dto.dart';
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

    dbQuery.where((p) => p.deletedAt.isNull());

    if (query != null && query.isNotEmpty) {
      final searchTerm = '%$query%';
      dbQuery.where(
        (p) => p.name.like(searchTerm) | p.barcode.like(searchTerm),
      );
    }

    // Keyset pagination: cursor is the last item's id from previous page.
    // ORDER BY id is stable and consistent with UUID string comparison.
    if (cursor != null) {
      dbQuery.where((p) => p.id.isBiggerThanValue(cursor));
    }

    dbQuery.orderBy([(p) => drift.OrderingTerm(expression: p.id)]);
    // Fetch limit+1 to determine if more pages exist — no full table scan.
    dbQuery.limit(limit + 1);

    final records = await dbQuery.get();

    final hasMore = records.length > limit;
    final items = records.take(limit).map((r) => r.toDomain()).toList();
    final nextCursor = hasMore ? items.last.id : null;

    return ProductPage(items: items, nextCursor: nextCursor, hasMore: hasMore);
  }

  @override
  Future<product_domain.Product> createProduct({
    required String name,
    required String unitPrice,
    String? barcode,
    int? currentStock,
  }) async {
    final normalizedBarcode = _normalizeBarcode(barcode);
    final id = const Uuid().v4();
    final now = DateTime.now();
    final product = product_domain.Product(
      id: id,
      name: name,
      unitPrice: Decimal.parse(unitPrice),
      barcode: normalizedBarcode,
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
            barcode: normalizedBarcode != null
                ? drift.Value(normalizedBarcode)
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
      productPayload: ProductSyncItemDto(
        id: id,
        name: name,
        barcode: normalizedBarcode,
        unitPrice: unitPrice,
        currentStock: currentStock,
        clientUpdatedAt: now.toUtc().toIso8601String(),
      ).toJson(),
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
    final updatedBarcode = barcode != null
        ? _normalizeBarcode(barcode)
        : current.barcode;
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
      productPayload: ProductSyncItemDto(
        id: id,
        name: updatedName,
        barcode: updatedBarcode,
        unitPrice: updatedPrice,
        currentStock: updatedStock,
        clientUpdatedAt: now.toUtc().toIso8601String(),
      ).toJson(),
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

    final current = await (db.select(
      db.products,
    )..where((p) => p.id.equals(id))).getSingleOrNull();
    if (current == null) return;

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
      productPayload: ProductSyncItemDto(
        id: id,
        name: current.name,
        barcode: current.barcode,
        unitPrice: current.unitPrice,
        currentStock: current.currentStock,
        clientUpdatedAt: now.toUtc().toIso8601String(),
        deleted: true,
      ).toJson(),
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
    final normalized = _normalizeBarcode(barcode);
    if (normalized == null) return null;
    final record =
        await (db.select(db.products)
              ..where((p) => p.barcode.equals(normalized))
              ..where((p) => p.deletedAt.isNull()))
            .getSingleOrNull();
    return record?.toDomain();
  }

  /// Strips whitespace and GS1 control characters from a barcode.
  /// Returns null if the result is empty.
  static String? _normalizeBarcode(String? raw) {
    if (raw == null) return null;
    final cleaned = raw.trim().replaceAll(RegExp(r'[\x00-\x1F\x7F]'), '');
    return cleaned.isEmpty ? null : cleaned;
  }
}
