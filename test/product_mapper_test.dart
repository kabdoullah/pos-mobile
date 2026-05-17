import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_models/product_dto.dart';
import 'package:mobile/features/catalog/data/mappers/product_mappers.dart';
import 'package:mobile/features/catalog/domain/entities/product.dart';

void main() {
  group('ProductDto → domain.Product mappers', () {
    test('ProductDto.toDomain() converts correctly', () {
      final now = DateTime.now().toIso8601String();
      final dto = ProductDto(
        id: 'prod-1',
        storeId: 'store-1',
        name: 'Test Product',
        barcode: '1234567890123',
        unitPrice: '1500.00',
        currentStock: 100,
        createdAt: now,
        updatedAt: now,
        deletedAt: null,
      );

      final domain = dto.toDomain();

      expect(domain.id, equals('prod-1'));
      expect(domain.name, equals('Test Product'));
      expect(domain.unitPrice, equals('1500.00'));
      expect(domain.barcode, equals('1234567890123'));
      expect(domain.currentStock, equals(100));
      expect(domain.updatedAt, isA<DateTime>());
      expect(domain.deletedAt, isNull);
    });

    test('ProductDto.toDomain() preserves decimal precision', () {
      final dto = ProductDto(
        id: 'prod-1',
        storeId: 'store-1',
        name: 'Expensive Item',
        unitPrice: '12345678.99',
        createdAt: DateTime.now().toIso8601String(),
        updatedAt: DateTime.now().toIso8601String(),
      );

      final domain = dto.toDomain();

      expect(domain.unitPrice, equals('12345678.99'));
    });

    test('ProductDto.toDomain() handles soft delete', () {
      final deletedAt = DateTime.now().toIso8601String();
      final dto = ProductDto(
        id: 'prod-1',
        storeId: 'store-1',
        name: 'Deleted Product',
        unitPrice: '1000.00',
        createdAt: DateTime.now().toIso8601String(),
        updatedAt: DateTime.now().toIso8601String(),
        deletedAt: deletedAt,
      );

      final domain = dto.toDomain();

      expect(domain.deletedAt, isNotNull);
      expect(domain.deletedAt, isA<DateTime>());
    });

    test('ProductDto → domain → DTO round-trip preserves data', () {
      final now = DateTime.now().toIso8601String();
      final originalDto = ProductDto(
        id: 'prod-1',
        storeId: 'store-1',
        name: 'Test Product',
        barcode: '1234567890123',
        unitPrice: '9999.99',
        currentStock: 50,
        createdAt: now,
        updatedAt: now,
        deletedAt: null,
      );

      // DTO → domain → createDto
      final domain = originalDto.toDomain();
      final createDto = domain.toCreateDto();

      expect(createDto.name, equals(originalDto.name));
      expect(createDto.barcode, equals(originalDto.barcode));
      expect(createDto.unitPrice, equals(originalDto.unitPrice));
      expect(createDto.currentStock, equals(originalDto.currentStock));
    });

    test('null optional fields handled correctly', () {
      final dto = ProductDto(
        id: 'prod-1',
        storeId: 'store-1',
        name: 'Simple Product',
        unitPrice: '500.00',
        createdAt: DateTime.now().toIso8601String(),
        updatedAt: DateTime.now().toIso8601String(),
      );

      final domain = dto.toDomain();

      expect(domain.barcode, isNull);
      expect(domain.currentStock, isNull);
      expect(domain.deletedAt, isNull);
    });
  });
}
