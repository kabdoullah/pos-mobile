import 'package:decimal/decimal.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';
import '../../domain/entities/cart_item.dart';
import '../../../catalog/domain/entities/product.dart';

part 'cart_provider.g.dart';

/// CartState holds the current shopping cart items.
class CartState {

  const CartState({required this.items});
  final List<CartItem> items;

  /// Total amount in FCFA (sum of all line totals).
  Decimal get total =>
      items.fold(Decimal.zero, (sum, item) => sum + item.lineTotal);

  /// Item count (unique products).
  int get itemCount => items.length;

  /// Whether cart is empty.
  bool get isEmpty => items.isEmpty;

  CartState copyWith({List<CartItem>? items}) {
    return CartState(items: items ?? this.items);
  }
}

/// CartNotifier manages shopping cart state.
@riverpod
class Cart extends _$Cart {
  @override
  CartState build() => const CartState(items: []);

  /// Add a product to cart (or increment qty if already exists).
  void addItem(Product product) {
    final existingIndex = state.items.indexWhere(
      (item) => item.productId == product.id,
    );

    if (existingIndex >= 0) {
      final existing = state.items[existingIndex];
      final updated = CartItem(
        productId: existing.productId,
        productName: existing.productName,
        unitPrice: existing.unitPrice,
        quantity: existing.quantity + 1,
      );
      final newItems = [...state.items];
      newItems[existingIndex] = updated;
      state = state.copyWith(items: newItems);
    } else {
      final newItem = CartItem(
        productId: product.id,
        productName: product.name,
        unitPrice: product.unitPrice,
        quantity: 1,
      );
      state = state.copyWith(items: [...state.items, newItem]);
    }
  }

  /// Remove product from cart by product ID.
  void removeItem(String productId) {
    final newItems = state.items
        .where((item) => item.productId != productId)
        .toList();
    state = state.copyWith(items: newItems);
  }

  /// Update quantity for a product (remove if qty ≤ 0).
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
      final updated = CartItem(
        productId: item.productId,
        productName: item.productName,
        unitPrice: item.unitPrice,
        quantity: qty,
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
