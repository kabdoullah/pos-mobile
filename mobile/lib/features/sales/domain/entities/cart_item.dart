import 'package:freezed_annotation/freezed_annotation.dart';

part 'cart_item.freezed.dart';

/// CartItem entity — represents a product line in a shopping cart.
@freezed
sealed class CartItem with _$CartItem {
  const factory CartItem({
    required String productId,
    required String productName,
    required String unitPrice, // FCFA stored as string (decimal precision)
    required int quantity,
  }) = _CartItem;

  /// Line total: quantity × unitPrice (both in FCFA).
  double get lineTotal => quantity * double.parse(unitPrice);

  const CartItem._();
}
