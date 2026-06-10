import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/cart_item.dart';
import '../../../catalog/domain/entities/product.dart';

part 'cart_provider.g.dart';

/// CartState holds the current shopping cart items.
class CartState {
  /// Creates a new CartState with the given list of cart items.
  const CartState({required this.items});

  /// Current items in the cart.
  final List<CartItem> items;

  /// Total amount in FCFA (sum of all line totals).
  Decimal get total =>
      items.fold(Decimal.zero, (sum, item) => sum + item.lineTotal);

  /// Item count (unique products).
  int get itemCount => items.length;

  /// Whether cart is empty.
  bool get isEmpty => items.isEmpty;

  /// Returns a copy of this state with updated values.
  CartState copyWith({List<CartItem>? items}) {
    return CartState(items: items ?? this.items);
  }
}

/// CartNotifier manages shopping cart state.
@riverpod
class Cart extends _$Cart {
  @override
  CartState build() => const CartState(items: []);

  /// Add a product to cart (or increment qty if already in cart).
  /// Returns false if stock would be exceeded, true otherwise.
  bool addItem(Product product) {
    final existingIndex = state.items.indexWhere(
      (item) => item.productId == product.id,
    );

    if (existingIndex >= 0) {
      final existing = state.items[existingIndex];
      final newQty = existing.quantity + 1;
      if (product.currentStock != null && newQty > product.currentStock!) {
        return false;
      }
      final updated = CartItem(
        productId: existing.productId,
        productName: existing.productName,
        unitPrice: existing.unitPrice,
        quantity: newQty,
        availableStock: product.currentStock ?? existing.availableStock,
      );
      final newItems = [...state.items];
      newItems[existingIndex] = updated;
      state = state.copyWith(items: newItems);
    } else {
      if (product.currentStock != null && product.currentStock! < 1) {
        return false;
      }
      final newItem = CartItem(
        productId: product.id,
        productName: product.name,
        unitPrice: product.unitPrice,
        quantity: 1,
        availableStock: product.currentStock,
      );
      state = state.copyWith(items: [...state.items, newItem]);
    }
    return true;
  }

  /// Remove product from cart by product ID.
  void removeItem(String productId) {
    final newItems = state.items
        .where((item) => item.productId != productId)
        .toList();
    state = state.copyWith(items: newItems);
  }

  /// Update quantity for a product (remove if qty ≤ 0, clamp to available stock).
  void updateQuantity(String productId, int qty) {
    if (qty <= 0) {
      removeItem(productId);
      return;
    }

    final itemIndex = state.items.indexWhere(
      (item) => item.productId == productId,
    );
    if (itemIndex >= 0) {
      final item = state.items[itemIndex];
      final clamped = item.availableStock != null
          ? qty.clamp(1, item.availableStock!)
          : qty;
      final updated = CartItem(
        productId: item.productId,
        productName: item.productName,
        unitPrice: item.unitPrice,
        quantity: clamped,
        availableStock: item.availableStock,
      );
      final newItems = [...state.items];
      newItems[itemIndex] = updated;
      state = state.copyWith(items: newItems);
    }
  }

  /// Clear all items from cart.
  void clear() {
    state = const CartState(items: []);
  }
}
