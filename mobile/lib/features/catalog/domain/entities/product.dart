import 'package:freezed_annotation/freezed_annotation.dart';

part 'product.freezed.dart';

/// Product entity — immutable product model.
@freezed
sealed class Product with _$Product {
  const factory Product({
    required String id,
    required String name,
    required String unitPrice, // FCFA stored as string (decimal precision)
    String? barcode,
    int? currentStock,
  }) = _Product;
}
