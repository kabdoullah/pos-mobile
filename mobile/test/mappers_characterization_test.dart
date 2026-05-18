import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_models/product_dto.dart';
import 'package:mobile/core/network/api_models/sale_dto.dart';
import 'package:mobile/core/network/api_models/store_dto.dart';
import 'package:mobile/features/auth/data/models/store_mappers.dart';
import 'package:mobile/features/auth/domain/entities/store.dart';
import 'package:mobile/features/catalog/data/models/product_mappers.dart';
import 'package:mobile/features/catalog/domain/entities/product.dart'
    as domain_product;
import 'package:mobile/features/sales/data/models/sale_mappers.dart';
import 'package:mobile/features/sales/domain/entities/sale.dart' as domain_sale;

void main() {
  group('Mappers Characterization Tests', () {
    group('Store Mappers', () {
      test('StoreDtoToDomain: maps DTO to domain correctly', () {
        const dto = StoreDto(
          id: 'store-1',
          ownerId: 'owner-1',
          name: 'Test Store',
          address: '123 Main St',
          ncc: 'NCC-123',
          vatSubject: true,
          receiptFooterText: 'Thank you!',
          nextReceiptNumber: 1,
          createdAt: '2025-01-01T00:00:00Z',
          updatedAt: '2025-01-01T00:00:00Z',
        );

        final result = dto.toDomain();

        expect(result.name, 'Test Store');
        expect(result.address, '123 Main St');
        expect(result.ncc, 'NCC-123');
        expect(result.isSubjectToVat, true);
        expect(result.receiptFooterText, 'Thank you!');
      });

      test('StoreUpdateDtoMapper: maps domain to update DTO', () {
        const domain = Store(
          name: 'Updated Store',
          address: '456 Oak Ave',
          ncc: 'NCC-456',
          isSubjectToVat: false,
          receiptFooterText: 'Goodbye!',
        );

        final result = domain.toUpdateDto();

        expect(result.name, 'Updated Store');
        expect(result.address, '456 Oak Ave');
        expect(result.ncc, 'NCC-456');
        expect(result.vatSubject, false);
        expect(result.receiptFooterText, 'Goodbye!');
      });

      test('StoreCreateDtoMapper: maps domain to create DTO', () {
        const domain = Store(
          name: 'New Store',
          address: '789 Pine Rd',
          ncc: 'NCC-789',
          isSubjectToVat: true,
          receiptFooterText: 'Welcome!',
        );

        final result = domain.toCreateDto();

        expect(result.name, 'New Store');
        expect(result.address, '789 Pine Rd');
        expect(result.ncc, 'NCC-789');
        expect(result.vatSubject, true);
        expect(result.receiptFooterText, 'Welcome!');
      });

      test('StoreDtoToDomain with null optional fields', () {
        const dto = StoreDto(
          id: 'store-1',
          ownerId: 'owner-1',
          name: 'Minimal Store',
          address: null,
          ncc: null,
          vatSubject: false,
          receiptFooterText: null,
          nextReceiptNumber: 0,
          createdAt: '2025-01-01T00:00:00Z',
          updatedAt: '2025-01-01T00:00:00Z',
        );

        final result = dto.toDomain();

        expect(result.name, 'Minimal Store');
        expect(result.address, null);
        expect(result.ncc, null);
        expect(result.isSubjectToVat, false);
        expect(result.receiptFooterText, null);
      });
    });

    group('Product Mappers - Monetary Precision', () {
      test('ProductDtoToDomain: preserves unitPrice decimal precision', () {
        const testCases = [
          '1234567.89',
          '0.00',
          '0.50',
          '0.05',
          '999999999.99',
          '1.00',
          '100',
        ];

        for (final price in testCases) {
          final dto = ProductDto(
            id: 'prod-1',
            storeId: 'store-1',
            name: 'Test Product',
            barcode: null,
            unitPrice: price,
            currentStock: 10,
            createdAt: '2025-01-01T00:00:00Z',
            updatedAt: '2025-01-01T00:00:00Z',
            deletedAt: null,
          );

          final domain = dto.toDomain();

          expect(
            domain.unitPrice,
            Decimal.parse(price),
            reason: 'Price $price should be preserved as Decimal',
          );
        }
      });

      test(
        'DomainProductToDrift: preserves unitPrice through drift companion',
        () {
          final domain = domain_product.Product(
            id: 'prod-1',
            name: 'Test Product',
            unitPrice: Decimal.parse('1234567.89'),
            barcode: 'BAR-123',
            currentStock: 50,
            updatedAt: DateTime(2025, 1, 1),
            deletedAt: null,
          );

          expect(domain.toDriftCompanion().unitPrice.value, '1234567.89');
        },
      );

      test(
        'ProductDtoToDomain → DomainProductToDrift: complete round-trip',
        () {
          const dto = ProductDto(
            id: 'prod-1',
            storeId: 'store-1',
            name: 'Test Product',
            barcode: 'BAR-001',
            unitPrice: '1234567.89',
            currentStock: 25,
            createdAt: '2025-01-01T00:00:00Z',
            updatedAt: '2025-01-01T12:00:00Z',
            deletedAt: null,
          );

          final domain = dto.toDomain();
          final companion = domain.toDriftCompanion();

          expect(companion.unitPrice.value, '1234567.89');
          expect(companion.name.value, 'Test Product');
          expect(companion.barcode.value, 'BAR-001');
          expect(companion.currentStock.value, 25);
        },
      );

      test('Product mappers with null optional fields', () {
        const dto = ProductDto(
          id: 'prod-2',
          storeId: 'store-1',
          name: 'Minimal Product',
          barcode: null,
          unitPrice: '100.00',
          currentStock: null,
          createdAt: '2025-01-01T00:00:00Z',
          updatedAt: '2025-01-01T00:00:00Z',
          deletedAt: null,
        );

        final domain = dto.toDomain();

        expect(domain.barcode, null);
        expect(domain.currentStock, null);
      });

      test('DomainProductCreateDtoMapper: preserves unitPrice', () {
        final domain = domain_product.Product(
          id: 'prod-1',
          name: 'New Product',
          unitPrice: Decimal.parse('1234567.89'),
          barcode: 'BAR-NEW',
          currentStock: 100,
          updatedAt: DateTime(2025, 1, 1),
          deletedAt: null,
        );

        final dto = domain.toCreateDto();

        expect(dto.unitPrice, '1234567.89');
        expect(dto.name, 'New Product');
        expect(dto.barcode, 'BAR-NEW');
      });

      test('DomainProductUpdateDtoMapper: preserves unitPrice', () {
        final domain = domain_product.Product(
          id: 'prod-1',
          name: 'Updated Product',
          unitPrice: '999.99',
          barcode: null,
          currentStock: 50,
          updatedAt: DateTime(2025, 1, 1),
          deletedAt: null,
        );

        final dto = domain.toUpdateDto();

        expect(dto.unitPrice, '999.99');
        expect(dto.name, 'Updated Product');
      });
    });

    group('Sale Mappers - Monetary Precision', () {
      test('SaleDtoToDomain: preserves monetary amounts', () {
        const testCases = [
          ('1234567.89', '123456.78'),
          ('0.00', '0.00'),
          ('0.50', '0.05'),
          ('999999999.99', '99999999.99'),
          ('1.00', '0.10'),
        ];

        for (final (totalAmount, vatAmount) in testCases) {
          final dto = SaleDto(
            id: 'sale-1',
            storeId: 'store-1',
            receiptNumber: 1,
            totalAmount: totalAmount,
            vatAmount: vatAmount,
            paymentMethod: 'cash',
            cashAmount: totalAmount,
            mobileMoneyAmount: null,
            createdAt: '2025-01-01T12:30:00Z',
            syncedAt: '2025-01-01T12:30:00Z',
            items: const [],
          );

          final domain = dto.toDomain();

          expect(
            domain.totalAmount,
            Decimal.parse(totalAmount),
            reason: 'Total $totalAmount should be preserved as Decimal',
          );
          expect(
            domain.vatAmount,
            Decimal.parse(vatAmount),
            reason: 'VAT $vatAmount should be preserved as Decimal',
          );
        }
      });

      test('SaleDtoToDomain: payment method enum conversion', () {
        const paymentMethodTests = [
          ('cash', domain_sale.PaymentMethod.cash),
          ('mobile_money_orange', domain_sale.PaymentMethod.orangeMoney),
          ('mobile_money_mtn', domain_sale.PaymentMethod.mtn),
          ('mobile_money_wave', domain_sale.PaymentMethod.wave),
          ('mixed', domain_sale.PaymentMethod.mixed),
        ];

        for (final (apiMethod, expectedEnum) in paymentMethodTests) {
          final dto = SaleDto(
            id: 'sale-1',
            storeId: 'store-1',
            receiptNumber: 1,
            totalAmount: '100.00',
            vatAmount: '10.00',
            paymentMethod: apiMethod,
            createdAt: '2025-01-01T12:30:00Z',
            syncedAt: '2025-01-01T12:30:00Z',
            items: const [],
          );

          final domain = dto.toDomain();

          expect(
            domain.paymentMethod,
            expectedEnum,
            reason: 'Payment method $apiMethod should map to $expectedEnum',
          );
        }
      });

      test('DomainSaleToDrift: preserves monetary amounts', () {
        final domain = domain_sale.Sale(
          id: 'sale-1',
          receiptNumber: 1,
          totalAmount: Decimal.parse('1234567.89'),
          vatAmount: Decimal.parse('123456.78'),
          paymentMethod: domain_sale.PaymentMethod.cash,
          createdAt: DateTime(2025, 1, 1, 12, 30),
        );

        final companion = domain.toDriftCompanion();

        expect(companion.totalAmount.value, '1234567.89');
        expect(companion.vatAmount.value, '123456.78');
      });

      test('DomainSaleToDrift: enum to string conversion', () {
        final enumTests = [
          (domain_sale.PaymentMethod.cash, 'cash'),
          (domain_sale.PaymentMethod.orangeMoney, 'mobile_money_orange'),
          (domain_sale.PaymentMethod.mtn, 'mobile_money_mtn'),
          (domain_sale.PaymentMethod.wave, 'mobile_money_wave'),
          (domain_sale.PaymentMethod.mixed, 'mixed'),
        ];

        for (final (domainEnum, expectedString) in enumTests) {
          final domain = domain_sale.Sale(
            id: 'sale-1',
            receiptNumber: 1,
            totalAmount: '100.00',
            vatAmount: '10.00',
            paymentMethod: domainEnum,
            createdAt: DateTime(2025, 1, 1),
          );

          final companion = domain.toDriftCompanion();

          expect(
            companion.paymentMethod.value,
            expectedString,
            reason: '$domainEnum should map to $expectedString',
          );
        }
      });

      test('SaleDtoToDomain → DomainSaleToDrift: complete round-trip', () {
        const dto = SaleDto(
          id: 'sale-123',
          storeId: 'store-1',
          receiptNumber: 42,
          totalAmount: '50000.50',
          vatAmount: '5000.05',
          paymentMethod: 'mixed',
          cashAmount: '25000.25',
          mobileMoneyAmount: '25000.25',
          createdAt: '2025-01-15T14:30:00Z',
          syncedAt: '2025-01-15T14:30:00Z',
          items: [],
        );

        final domain = dto.toDomain();
        final companion = domain.toDriftCompanion();

        expect(companion.totalAmount.value, '50000.50');
        expect(companion.vatAmount.value, '5000.05');
        expect(companion.paymentMethod.value, 'mixed');
        expect(companion.receiptNumber.value, 42);
      });

      test('DomainSaleCreateDtoMapper: monetary precision in request', () {
        final domain = domain_sale.Sale(
          id: 'sale-1',
          receiptNumber: 1,
          totalAmount: '1234567.89',
          vatAmount: '123456.78',
          paymentMethod: domain_sale.PaymentMethod.mixed,
          createdAt: DateTime(2025, 1, 1, 12, 30),
        );

        final dto = domain.toCreateDto(
          items: const [],
          cashAmount: '600000.00',
          mobileMoneyAmount: '634567.89',
        );

        expect(dto.totalAmount, '1234567.89');
        expect(dto.vatAmount, '123456.78');
        expect(dto.paymentMethod, PaymentMethodDto.mixed);
        expect(dto.cashAmount, '600000.00');
        expect(dto.mobileMoneyAmount, '634567.89');
      });

      test('Sale mappers with minimal fields', () {
        const dto = SaleDto(
          id: 'sale-2',
          storeId: 'store-1',
          receiptNumber: null,
          totalAmount: '100.00',
          vatAmount: '0.00',
          paymentMethod: 'cash',
          cashAmount: null,
          mobileMoneyAmount: null,
          createdAt: '2025-01-01T00:00:00Z',
          syncedAt: '2025-01-01T00:00:00Z',
          items: [],
        );

        final domain = dto.toDomain();

        expect(domain.receiptNumber, 0);
        expect(domain.totalAmount, '100.00');
        expect(domain.vatAmount, '0.00');
        expect(domain.paymentMethod, domain_sale.PaymentMethod.cash);
      });
    });

    group('Payment Method Enum Mapping', () {
      test('All PaymentMethod enum values are covered', () {
        final allMethods = [
          domain_sale.PaymentMethod.cash,
          domain_sale.PaymentMethod.orangeMoney,
          domain_sale.PaymentMethod.mtn,
          domain_sale.PaymentMethod.wave,
          domain_sale.PaymentMethod.mixed,
        ];

        for (final method in allMethods) {
          final domain = domain_sale.Sale(
            id: 'test-id',
            receiptNumber: 0,
            totalAmount: '0.00',
            vatAmount: '0.00',
            paymentMethod: method,
            createdAt: DateTime.now(),
          );

          final companion = domain.toDriftCompanion();
          expect(
            companion.paymentMethod.present,
            true,
            reason: 'Payment method $method should map to string',
          );
          expect(companion.paymentMethod.value, isA<String>());
        }
      });
    });
  });
}
