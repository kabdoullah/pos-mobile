import 'package:drift/drift.dart' as drift;

import '../../../../core/network/api_models/product_dto.dart';
import '../../../../database/app_database.dart' as drift_db;
import '../../../catalog/domain/entities/product.dart' as domain;

/// Maps ProductDto (API) → domain.Product (domain).
extension ProductDtoToDomain on ProductDto {
  /// Converts API DTO to domain entity.
  domain.Product toDomain() => domain.Product(
    id: id,
    name: name,
    unitPrice: unitPrice,
    barcode: barcode,
    currentStock: currentStock,
    updatedAt: DateTime.parse(updatedAt),
    deletedAt: deletedAt != null ? DateTime.parse(deletedAt!) : null,
  );
}

/// Maps domain.Product → drift ProductsCompanion (drift).
extension DomainProductToDrift on domain.Product {
  /// Converts domain entity to drift companion.
  drift_db.ProductsCompanion toDriftCompanion() => drift_db.ProductsCompanion(
    id: drift.Value(id),
    name: drift.Value(name),
    barcode: barcode != null
        ? drift.Value(barcode)
        : const drift.Value.absent(),
    unitPrice: drift.Value(unitPrice),
    currentStock: currentStock != null
        ? drift.Value(currentStock)
        : const drift.Value.absent(),
    dirty: const drift.Value(false),
    updatedAt: drift.Value(updatedAt),
    deletedAt: deletedAt != null
        ? drift.Value(deletedAt)
        : const drift.Value.absent(),
  );
}

/// Maps drift Product row → domain.Product.
extension DriftProductToDomain on drift_db.Product {
  /// Converts drift row to domain entity.
  domain.Product toDomain() => domain.Product(
    id: id,
    name: name,
    unitPrice: unitPrice,
    barcode: barcode,
    currentStock: currentStock,
    updatedAt: updatedAt,
    deletedAt: deletedAt,
  );
}

/// Maps domain.Product → ProductCreateDto (API request).
extension DomainProductCreateDtoMapper on domain.Product {
  /// Converts domain entity to create request DTO.
  ProductCreateDto toCreateDto() => ProductCreateDto(
    name: name,
    barcode: barcode,
    unitPrice: unitPrice,
    currentStock: currentStock,
  );
}

/// Maps domain.Product → ProductUpdateDto (API request).
extension DomainProductUpdateDtoMapper on domain.Product {
  /// Converts domain entity to update request DTO.
  ProductUpdateDto toUpdateDto() => ProductUpdateDto(
    name: name,
    barcode: barcode,
    unitPrice: unitPrice,
    currentStock: currentStock,
  );
}
