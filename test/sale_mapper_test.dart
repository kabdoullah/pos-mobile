import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_models/sale_dto.dart';
import 'package:mobile/features/sales/data/mappers/sale_mappers.dart';
import 'package:mobile/features/sales/domain/entities/sale.dart';

void main() {
  group('SaleDto → domain.Sale mappers', () {
    test('SaleDto.toDomain() converts correctly', () {
      final now = DateTime.now().toIso8601String();
      final dto = SaleDto(
        id: 'sale-1',
        storeId: 'store-1',
        receiptNumber: 1,
        totalAmount: '5000.00',
        vatAmount: '500.00',
        paymentMethod: 'cash',
        createdAt: now,
        syncedAt: now,
        items: [],
      );

      final domain = dto.toDomain();

      expect(domain.id, equals('sale-1'));
      expect(domain.receiptNumber, equals(1));
      expect(domain.totalAmount, equals('5000.00'));
      expect(domain.vatAmount, equals('500.00'));
      expect(domain.paymentMethod, equals(PaymentMethod.cash));
      expect(domain.createdAt, isA<DateTime>());
    });

    test('SaleDto.toDomain() preserves decimal precision for amounts', () {
      final dto = SaleDto(
        id: 'sale-1',
        storeId: 'store-1',
        totalAmount: '123456789.99',
        vatAmount: '12345678.99',
        paymentMethod: 'cash',
        createdAt: DateTime.now().toIso8601String(),
        syncedAt: DateTime.now().toIso8601String(),
        items: [],
      );

      final domain = dto.toDomain();

      expect(domain.totalAmount, equals('123456789.99'));
      expect(domain.vatAmount, equals('12345678.99'));
    });

    test('SaleDto.toDomain() maps all payment methods', () {
      final testCases = [
        ('cash', PaymentMethod.cash),
        ('mobile_money_orange', PaymentMethod.orangeMoney),
        ('mobile_money_mtn', PaymentMethod.mtn),
        ('mobile_money_wave', PaymentMethod.wave),
        ('mixed', PaymentMethod.mixed),
      ];

      for (final (dtoMethod, expectedMethod) in testCases) {
        final dto = SaleDto(
          id: 'sale-$dtoMethod',
          storeId: 'store-1',
          totalAmount: '1000.00',
          vatAmount: '0.00',
          paymentMethod: dtoMethod,
          createdAt: DateTime.now().toIso8601String(),
          syncedAt: DateTime.now().toIso8601String(),
          items: [],
        );

        final domain = dto.toDomain();
        expect(domain.paymentMethod, equals(expectedMethod),
            reason: 'Failed for payment method: $dtoMethod');
      }
    });

    test('SaleDto.toDomain() handles null receipt number', () {
      final dto = SaleDto(
        id: 'sale-1',
        storeId: 'store-1',
        receiptNumber: null,
        totalAmount: '1000.00',
        vatAmount: '0.00',
        paymentMethod: 'cash',
        createdAt: DateTime.now().toIso8601String(),
        syncedAt: DateTime.now().toIso8601String(),
        items: [],
      );

      final domain = dto.toDomain();

      expect(domain.receiptNumber, equals(0));
    });

    test('domain.Sale → SaleCreateDto round-trip preserves data', () {
      final now = DateTime.now();
      final domain = Sale(
        id: 'sale-1',
        receiptNumber: 1,
        totalAmount: '5000.00',
        vatAmount: '500.00',
        paymentMethod: PaymentMethod.cash,
        createdAt: now,
      );

      final createDto = domain.toCreateDto(items: []);

      expect(createDto.id, equals(domain.id));
      expect(createDto.totalAmount, equals(domain.totalAmount));
      expect(createDto.vatAmount, equals(domain.vatAmount));
      expect(createDto.paymentMethod, equals(PaymentMethodDto.cash));
    });

    test('domain.Sale → SaleCreateDto converts payment methods', () {
      final testCases = [
        (PaymentMethod.cash, PaymentMethodDto.cash),
        (PaymentMethod.orangeMoney, PaymentMethodDto.mobileMoneyOrange),
        (PaymentMethod.mtn, PaymentMethodDto.mobileMoneyMtn),
        (PaymentMethod.wave, PaymentMethodDto.mobileMoneyWave),
        (PaymentMethod.mixed, PaymentMethodDto.mixed),
      ];

      for (final (domainMethod, expectedDtoMethod) in testCases) {
        final domain = Sale(
          id: 'sale-1',
          receiptNumber: 1,
          totalAmount: '1000.00',
          vatAmount: '0.00',
          paymentMethod: domainMethod,
          createdAt: DateTime.now(),
        );

        final createDto = domain.toCreateDto(items: []);
        expect(createDto.paymentMethod, equals(expectedDtoMethod),
            reason: 'Failed for payment method: $domainMethod');
      }
    });
  });
}
