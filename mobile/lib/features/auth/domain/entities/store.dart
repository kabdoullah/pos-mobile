import 'package:freezed_annotation/freezed_annotation.dart';

part 'store.freezed.dart';

/// Store configuration for the merchant's shop.
///
/// Contains basic store info displayed on receipts and in settings.
@freezed
sealed class Store with _$Store {
  /// Creates a [Store].
  const factory Store({
    /// Store name (required).
    required String name,

    /// Store address (optional).
    String? address,

    /// Numéro de Compte Contribuable DGI (optional).
    String? ncc,

    /// Whether the store is subject to VAT (default: false).
    required bool isSubjectToVat,

    /// Custom footer text for receipts (optional).
    String? receiptFooterText,
  }) = _Store;
}
