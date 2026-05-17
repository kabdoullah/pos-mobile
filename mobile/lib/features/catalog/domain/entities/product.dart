import 'package:freezed_annotation/freezed_annotation.dart';

part 'product.freezed.dart';

/// Product entity — immutable product model.
@freezed
sealed class Product with _$Product {
  /// Creates a [Product].
  const factory Product({
    required String id,
    required String name,

    /// FCFA stored as string (decimal precision).
    required String unitPrice,
    String? barcode,
    int? currentStock,
    required DateTime updatedAt,
    DateTime? deletedAt,
  }) = _Product;
}
