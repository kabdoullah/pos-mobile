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

  /// Product found but stock is exhausted.
  stockExceeded,
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
    // Normalize: strip whitespace and GS1 control characters before any lookup.
    final normalized = barcode.trim().replaceAll(
      RegExp(r'[\x00-\x1F\x7F]'),
      '',
    );
    if (normalized.isEmpty) return ScanResult.notFound;

    final now = DateTime.now();
    final last = _lastScanTimes[normalized];
    if (last != null && now.difference(last) < _scanCooldown) {
      return ScanResult.cooldown;
    }
    _lastScanTimes[normalized] = now;
    _lastScanTimes.removeWhere((_, t) => now.difference(t) > _scanCooldown);

    final repo = ref.read(catalogRepositoryProvider);
    final product = await repo.getByBarcode(normalized);
    if (product == null) return ScanResult.notFound;

    if (!ref.mounted) return ScanResult.notFound;

    final cartState = ref.read(cartProvider);
    final alreadyInCart = cartState.items.any(
      (CartItem item) => item.productId == product.id,
    );

    final added = ref.read(cartProvider.notifier).addItem(product);
    if (!added) return ScanResult.stockExceeded;
    return alreadyInCart ? ScanResult.quantityIncremented : ScanResult.added;
  }
}
