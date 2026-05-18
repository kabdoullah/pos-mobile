import 'package:decimal/decimal.dart';

import '../entities/cart_item.dart';
import '../entities/sale.dart';
import '../repositories/sales_repository.dart';

/// Exception for create sale business rule violations.
class CreateSaleException implements Exception {
  /// Create an exception with a message.
  CreateSaleException(this.message);

  /// Error message.
  final String message;

  @override
  String toString() => 'CreateSaleException: $message';
}

/// Business logic for creating a sale.
/// Encapsulates all rules: validation, UUID generation, amount calculation.
class CreateSaleUseCase {
  /// Create a use case instance.
  CreateSaleUseCase({required this.repository});

  /// The repository for persisting sales.
  final SalesRepository repository;

  /// Create a sale from cart items and payment details.
  ///
  /// Validates:
  /// - Cart is not empty
  /// - Payment totals match sale total (especially for mixed payments)
  /// - All amounts are non-negative
  ///
  /// Generates a client-side UUID for idempotent sync.
  /// Persists the sale and items atomically via repository.
  Future<Sale> call({
    required List<CartItem> items,
    required Decimal totalAmount,
    required Decimal vatAmount,
    required PaymentMethod paymentMethod,
    Decimal? cashAmount,
    Decimal? mobileMoneyAmount,
  }) async {
    // Validation: cart not empty
    if (items.isEmpty) {
      throw CreateSaleException('Le panier est vide');
    }

    // Validation: amounts not negative
    if (totalAmount < Decimal.zero) {
      throw CreateSaleException('Montant total invalide');
    }
    if (vatAmount < Decimal.zero) {
      throw CreateSaleException('Montant TVA invalide');
    }

    // Recalculate total from items as double-check
    final calculatedTotal = items.fold<Decimal>(
      Decimal.zero,
      (sum, item) => sum + item.lineTotal,
    );
    if (calculatedTotal != totalAmount) {
      throw CreateSaleException(
        'Total panier ($calculatedTotal) ne correspond pas au montant fourni ($totalAmount)',
      );
    }

    // Validation: payment validation
    if (paymentMethod == PaymentMethod.mixed) {
      final cash = cashAmount ?? Decimal.zero;
      final mobileMoney = mobileMoneyAmount ?? Decimal.zero;
      final paymentTotal = cash + mobileMoney;

      if (paymentTotal != totalAmount) {
        throw CreateSaleException(
          'Total paiement ($paymentTotal) ne correspond pas au montant ($totalAmount)',
        );
      }
    }

    // Create sale via repository (which handles persistence + sync)
    return repository.createSale(
      items: items,
      totalAmount: totalAmount,
      vatAmount: vatAmount,
      paymentMethod: paymentMethod,
      cashAmount: cashAmount,
      mobileMoneyAmount: mobileMoneyAmount,
    );
  }
}
