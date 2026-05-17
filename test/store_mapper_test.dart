import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_models/store_dto.dart';
import 'package:mobile/features/auth/data/mappers/store_mappers.dart';
import 'package:mobile/features/auth/domain/entities/store.dart';

void main() {
  group('StoreDto → domain.Store mappers', () {
    test('StoreDto.toDomain() converts all fields correctly', () {
      final dto = StoreDto(
        id: 'store-1',
        ownerId: 'owner-1',
        name: 'My Store',
        address: '123 Main St',
        ncc: '1234567890123',
        vatSubject: true,
        receiptFooterText: 'Thank you for your business',
        nextReceiptNumber: 100,
        createdAt: DateTime.now().toIso8601String(),
        updatedAt: DateTime.now().toIso8601String(),
      );

      final domain = dto.toDomain();

      expect(domain.name, equals('My Store'));
      expect(domain.address, equals('123 Main St'));
      expect(domain.ncc, equals('1234567890123'));
      expect(domain.isSubjectToVat, equals(true));
      expect(domain.receiptFooterText,
          equals('Thank you for your business'));
    });

    test('StoreDto.toDomain() handles null optional fields', () {
      final dto = StoreDto(
        id: 'store-1',
        ownerId: 'owner-1',
        name: 'Simple Store',
        vatSubject: false,
        nextReceiptNumber: 1,
        createdAt: DateTime.now().toIso8601String(),
        updatedAt: DateTime.now().toIso8601String(),
      );

      final domain = dto.toDomain();

      expect(domain.address, isNull);
      expect(domain.ncc, isNull);
      expect(domain.receiptFooterText, isNull);
      expect(domain.isSubjectToVat, equals(false));
    });

    test('domain.Store → StoreUpdateDto round-trip preserves data', () {
      final domain = Store(
        name: 'Updated Store',
        address: '456 Oak Ave',
        ncc: '9876543210987',
        isSubjectToVat: true,
        receiptFooterText: 'Updated footer',
      );

      final updateDto = domain.toUpdateDto();

      expect(updateDto.name, equals(domain.name));
      expect(updateDto.address, equals(domain.address));
      expect(updateDto.ncc, equals(domain.ncc));
      expect(updateDto.vatSubject, equals(domain.isSubjectToVat));
      expect(updateDto.receiptFooterText,
          equals(domain.receiptFooterText));
    });

    test('domain.Store → StoreCreateDto round-trip preserves data', () {
      final domain = Store(
        name: 'New Store',
        address: '789 Pine Rd',
        ncc: '1111111111111',
        isSubjectToVat: false,
        receiptFooterText: 'Welcome to our store',
      );

      final createDto = domain.toCreateDto();

      expect(createDto.name, equals(domain.name));
      expect(createDto.address, equals(domain.address));
      expect(createDto.ncc, equals(domain.ncc));
      expect(createDto.vatSubject, equals(domain.isSubjectToVat));
      expect(createDto.receiptFooterText,
          equals(domain.receiptFooterText));
    });

    test('null optional fields in domain.Store handled correctly', () {
      final domain = Store(
        name: 'Minimal Store',
        isSubjectToVat: true,
      );

      final updateDto = domain.toUpdateDto();
      final createDto = domain.toCreateDto();

      expect(updateDto.address, isNull);
      expect(updateDto.ncc, isNull);
      expect(updateDto.receiptFooterText, isNull);

      expect(createDto.address, isNull);
      expect(createDto.ncc, isNull);
      expect(createDto.receiptFooterText, isNull);
    });
  });
}
