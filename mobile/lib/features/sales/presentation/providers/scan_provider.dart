import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../catalog/providers/catalog_di_providers.dart';
import '../../domain/entities/cart_item.dart';
import 'cart_provider.dart';

part 'scan_provider.g.dart';

/// Result of a barcode scan attempt.
enum ScanResult {
  /// Product added to cart for first time.
  added,

  /// Product quantity incremented (already in cart).
  quantityIncremented,

  /// Barcode not found in catalog.
  notFound,

  /// Same barcode scanned within cooldown window (2s).
  cooldown,
}

/// Manages barcode scanning: cooldown deduplication, catalog lookup, cart dispatch.
@riverpod
class ScanController extends _$ScanController {
  final Map<String, DateTime> _lastScanTimes = {};
  static const Duration _scanCooldown = Duration(seconds: 2);

  @override
  void build() {}

  /// Process a scanned barcode: check cooldown, look up in catalog, update cart.
  Future<ScanResult> scan(String barcode) async {
    final now = DateTime.now();
    final last = _lastScanTimes[barcode];
    if (last != null && now.difference(last) < _scanCooldown) {
      return ScanResult.cooldown;
    }
    _lastScanTimes[barcode] = now;

    final repo = ref.read(catalogRepositoryProvider);
    final product = await repo.getByBarcode(barcode);
    if (product == null) return ScanResult.notFound;

    if (!ref.mounted) return ScanResult.notFound;

    final cartState = ref.read(cartProvider);
    final alreadyInCart = cartState.items.any(
      (CartItem item) => item.productId == product.id,
    );

    ref.read(cartProvider.notifier).addItem(product);
    return alreadyInCart ? ScanResult.quantityIncremented : ScanResult.added;
  }
}
