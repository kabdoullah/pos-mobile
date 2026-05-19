import 'package:decimal/decimal.dart';
import 'package:freezed_annotation/freezed_annotation.dart';

part 'cart_item.freezed.dart';

/// CartItem entity — represents a product line in a shopping cart.
@freezed
sealed class CartItem with _$CartItem {
  const CartItem._();
  const factory CartItem({
    required String productId,
    required String productName,
    required Decimal unitPrice,
    required int quantity,
  }) = _CartItem;

  /// Line total: quantity × unitPrice (both in FCFA).
  Decimal get lineTotal => unitPrice * Decimal.fromInt(quantity);
}
