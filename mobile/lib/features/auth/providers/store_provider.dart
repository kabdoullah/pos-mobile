import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../data/models/store_mappers.dart';
import '../domain/entities/store.dart';
import 'auth_di_providers.dart';

part 'store_provider.g.dart';

/// Storage keys for Store data in flutter_secure_storage.
abstract class _StoreKeys {
  /// Store name key.
  static const String name = 'store_name';

  /// Store address key.
  static const String address = 'store_address';

  /// Store NCC (Numéro de Compte Contribuable) key.
  static const String ncc = 'store_ncc';

  /// Store VAT subject flag key.
  static const String isSubjectToVat = 'store_vat';

  /// Store receipt footer text key.
  static const String footerText = 'store_footer';
}

/// Provides access to the current store configuration.
///
/// Reads from and writes to flutter_secure_storage.

// keepAlive: store config is app-wide and must survive across screens.
// Without it, the provider auto-disposes during store setup (no widget
// watches it there) and `save()` throws setting state on a disposed notifier.
@Riverpod(keepAlive: true)
class StoreConfig extends _$StoreConfig {
  static const _storage = FlutterSecureStorage();

  @override
  Future<Store?> build() async {
    // Read store name from secure storage
    final name = await _storage.read(key: _StoreKeys.name);
    // If name is null, store has not been configured yet
    if (name == null) return null;

    // Read all other fields
    final address = await _storage.read(key: _StoreKeys.address);
    final ncc = await _storage.read(key: _StoreKeys.ncc);
    final isSubjectToVat = await _storage.read(key: _StoreKeys.isSubjectToVat);
    final footerText = await _storage.read(key: _StoreKeys.footerText);

    return Store(
      name: name,
      address: address,
      ncc: ncc,
      isSubjectToVat: isSubjectToVat == 'true',
      receiptFooterText: footerText,
    );
  }

  /// Persist store configuration locally then sync to backend.
  ///
  /// Local write always runs first. Backend PATCH follows — if it fails the
  /// exception propagates so the UI can display it (store name update is
  /// meaningful to the user and must reach the server).
  Future<void> save(Store store) async {
    await _storage.write(key: _StoreKeys.name, value: store.name);
    await _storage.write(key: _StoreKeys.address, value: store.address);
    await _storage.write(key: _StoreKeys.ncc, value: store.ncc);
    await _storage.write(
      key: _StoreKeys.isSubjectToVat,
      value: store.isSubjectToVat.toString(),
    );
    await _storage.write(
      key: _StoreKeys.footerText,
      value: store.receiptFooterText,
    );

    // Sync to backend (PATCH /api/v1/stores/me).
    final datasource = ref.read(storesRemoteDataSourceProvider);
    await datasource.updateStore(store.toUpdateDto());

    // Update state only after both local + remote succeed.
    state = AsyncData(store);
  }
}
