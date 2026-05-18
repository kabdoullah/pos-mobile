import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Decimal conversion — monetary boundary rules', () {
    test('Decimal.parse preserves precision that int.parse loses', () {
      expect(Decimal.parse('1234567.89').toString(), '1234567.89');
      expect(Decimal.parse('0.50').toString(), '0.5');
      expect(Decimal.parse('100').toString(), '100');
      expect(Decimal.parse('0.00').toString(), '0');
    });

    test('Decimal × int quantity produces correct line total', () {
      // ignore: prefer_const_declarations
      final price = Decimal.parse('1500');
      const qty = 3;
      expect(price * Decimal.fromInt(qty), Decimal.parse('4500'));
    });

    test('Decimal × int with decimal price', () {
      // ignore: prefer_const_declarations
      final price = Decimal.parse('1234.50');
      const qty = 2;
      expect(price * Decimal.fromInt(qty), Decimal.parse('2469.00'));
    });

    test('Decimal arithmetic for change calculation', () {
      final received = Decimal.parse('10000');
      final total = Decimal.parse('7500');
      expect(received - total, Decimal.parse('2500'));
    });

    test('Decimal comparison works for insufficient payment check', () {
      final received = Decimal.parse('5000');
      final total = Decimal.parse('7500');
      expect(received < total, isTrue);
    });

    test('Decimal.tryParse returns null on invalid input', () {
      expect(Decimal.tryParse('abc'), isNull);
      expect(Decimal.tryParse(''), isNull);
      expect(Decimal.tryParse('12.34.56'), isNull);
    });

    test('Decimal.tryParse returns value on valid input', () {
      expect(Decimal.tryParse('1500'), isNotNull);
      expect(Decimal.tryParse('0'), isNotNull);
    });

    test('toDouble() for NumberFormat is safe for FCFA amounts', () {
      final d = Decimal.parse('50000');
      expect(d.toDouble(), 50000.0);
    });

    test('vatAmount zero check: compare to Decimal.zero, not string', () {
      expect(Decimal.parse('0') == Decimal.zero, isTrue);
      expect(Decimal.parse('0.00') == Decimal.zero, isTrue);
      expect(Decimal.parse('500') == Decimal.zero, isFalse);
    });
  });
}
