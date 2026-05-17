import 'package:freezed_annotation/freezed_annotation.dart';

part 'product_dto.freezed.dart';
part 'product_dto.g.dart';

/// Product data transfer object from API.
@freezed
sealed class ProductDto with _$ProductDto {
  /// Creates a [ProductDto].
  const factory ProductDto({
    required String id,
    @JsonKey(name: 'store_id') required String storeId,
    required String name,
    String? barcode,

    /// Price in FCFA, received as string from API.
    @JsonKey(name: 'unit_price') required String unitPrice,
    @JsonKey(name: 'current_stock') int? currentStock,
    @JsonKey(name: 'created_at') required String createdAt,
    @JsonKey(name: 'updated_at') required String updatedAt,
    @JsonKey(name: 'deleted_at') String? deletedAt,
  }) = _ProductDto;

  factory ProductDto.fromJson(Map<String, dynamic> json) =>
      _$ProductDtoFromJson(json);
}

/// Request to create a product.
@freezed
sealed class ProductCreateDto with _$ProductCreateDto {
  /// Creates a [ProductCreateDto].
  const factory ProductCreateDto({
    required String name,
    String? barcode,

    /// Price in FCFA.
    @JsonKey(name: 'unit_price') required String unitPrice,
    @JsonKey(name: 'current_stock') int? currentStock,
  }) = _ProductCreateDto;

  factory ProductCreateDto.fromJson(Map<String, dynamic> json) =>
      _$ProductCreateDtoFromJson(json);
}

/// Request to update a product (PATCH).
@freezed
sealed class ProductUpdateDto with _$ProductUpdateDto {
  /// Creates a [ProductUpdateDto].
  const factory ProductUpdateDto({
    String? name,
    String? barcode,
    @JsonKey(name: 'unit_price') String? unitPrice,
    @JsonKey(name: 'current_stock') int? currentStock,
  }) = _ProductUpdateDto;

  factory ProductUpdateDto.fromJson(Map<String, dynamic> json) =>
      _$ProductUpdateDtoFromJson(json);
}
