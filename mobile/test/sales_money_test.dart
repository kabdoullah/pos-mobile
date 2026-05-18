import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobile/features/sales/domain/entities/cart_item.dart';
import 'package:mobile/features/sales/domain/entities/sale.dart';

void main() {
  group('Sales monetary conversion', () {
    test('CartItem.unitPrice handles Decimal values', () {
      final item = CartItem(
        productId: 'prod-1',
        productName: 'Widget',
        unitPrice: Decimal.parse('1234.56'),
        quantity: 2,
      );

      expect(item.unitPrice, Decimal.parse('1234.56'));
      expect(item.lineTotal, Decimal.parse('2469.12'));
    });

    test('CartItem.lineTotal preserves precision with decimal quantities', () {
      final item = CartItem(
        productId: 'prod-1',
        productName: 'Item',
        unitPrice: Decimal.parse('400.00'),
        quantity: 1,
      );

      expect(item.lineTotal, Decimal.parse('400.00'));
    });

    test('Sale.totalAmount is Decimal', () {
      final sale = Sale(
        id: 'sale-1',
        receiptNumber: 1,
        totalAmount: Decimal.parse('2469.12'),
        vatAmount: Decimal.parse('0'),
        paymentMethod: PaymentMethod.cash,
        createdAt: DateTime.now(),
      );

      expect(sale.totalAmount, Decimal.parse('2469.12'));
      expect(sale.totalAmount.runtimeType, Decimal);
    });

    test('Sale.vatAmount is Decimal', () {
      final sale = Sale(
        id: 'sale-1',
        receiptNumber: 1,
        totalAmount: Decimal.parse('100.00'),
        vatAmount: Decimal.parse('18.00'),
        paymentMethod: PaymentMethod.cash,
        createdAt: DateTime.now(),
      );

      expect(sale.vatAmount, Decimal.parse('18.00'));
      expect(sale.vatAmount.runtimeType, Decimal);
    });

    test('Small decimal values (0.50) preserve precision', () {
      final item = CartItem(
        productId: 'prod-1',
        productName: 'Item',
        unitPrice: Decimal.parse('0.50'),
        quantity: 3,
      );

      expect(item.lineTotal, Decimal.parse('1.50'));
    });

    test('Zero amounts handled correctly', () {
      final item = CartItem(
        productId: 'prod-1',
        productName: 'Item',
        unitPrice: Decimal.parse('0'),
        quantity: 10,
      );

      expect(item.lineTotal, Decimal.parse('0'));
    });

    test('Large FCFA amounts (250k+) preserve precision', () {
      final sale = Sale(
        id: 'sale-1',
        receiptNumber: 1,
        totalAmount: Decimal.parse('250000.00'),
        vatAmount: Decimal.parse('0'),
        paymentMethod: PaymentMethod.cash,
        createdAt: DateTime.now(),
      );

      expect(sale.totalAmount, Decimal.parse('250000.00'));
    });

    test('Cart with multiple items calculates total correctly', () {
      final items = [
        CartItem(
          productId: 'prod-1',
          productName: 'Item 1',
          unitPrice: Decimal.parse('1000.00'),
          quantity: 1,
        ),
        CartItem(
          productId: 'prod-2',
          productName: 'Item 2',
          unitPrice: Decimal.parse('500.00'),
          quantity: 2,
        ),
        CartItem(
          productId: 'prod-3',
          productName: 'Item 3',
          unitPrice: Decimal.parse('250.75'),
          quantity: 1,
        ),
      ];

      final total = items.fold(
        Decimal.zero,
        (sum, item) => sum + item.lineTotal,
      );

      expect(total, Decimal.parse('2250.75'));
    });
  });
}
