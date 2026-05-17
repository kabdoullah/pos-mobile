import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:mobile/core/storage/pin_storage.dart';

class MockSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  group('PinStorage', () {
    late MockSecureStorage mockStorage;
    late PinStorage pinStorage;

    setUp(() {
      mockStorage = MockSecureStorage();
      pinStorage = PinStorage(
        secureStorage: mockStorage,
        lockoutDuration: const Duration(seconds: 5),
      );
    });

    test('savePinHash stores hash and salt', () async {
      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockStorage.delete(key: any(named: 'key')),
      ).thenAnswer((_) async {});

      await pinStorage.savePinHash('1234');

      verify(
        () => mockStorage.write(
          key: 'pin_hash',
          value: any(named: 'value'),
        ),
      ).called(1);
      verify(
        () => mockStorage.write(
          key: 'pin_salt',
          value: any(named: 'value'),
        ),
      ).called(1);
      verify(
        () => mockStorage.write(key: 'pin_attempts', value: '0'),
      ).called(1);
    });

    test('hasPinConfigured returns true when PIN is set', () async {
      when(
        () => mockStorage.read(key: 'pin_hash'),
      ).thenAnswer((_) async => 'some_hash');

      final result = await pinStorage.hasPinConfigured();

      expect(result, isTrue);
    });

    test('hasPinConfigured returns false when PIN is not set', () async {
      when(
        () => mockStorage.read(key: 'pin_hash'),
      ).thenAnswer((_) async => null);

      final result = await pinStorage.hasPinConfigured();

      expect(result, isFalse);
    });

    test('getPinAttempts returns 0 when no key exists', () async {
      when(
        () => mockStorage.read(key: 'pin_attempts'),
      ).thenAnswer((_) async => null);

      final result = await pinStorage.getPinAttempts();

      expect(result, 0);
    });

    test('getPinAttempts parses stored integer', () async {
      when(
        () => mockStorage.read(key: 'pin_attempts'),
      ).thenAnswer((_) async => '3');

      final result = await pinStorage.getPinAttempts();

      expect(result, 3);
    });

    test('resetAttempts clears lockout and attempts', () async {
      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});
      when(
        () => mockStorage.delete(key: any(named: 'key')),
      ).thenAnswer((_) async {});

      await pinStorage.resetAttempts();

      verify(
        () => mockStorage.write(key: 'pin_attempts', value: '0'),
      ).called(1);
      verify(() => mockStorage.delete(key: 'pin_lockout_until')).called(1);
    });

    test('clearPin deletes all PIN-related keys', () async {
      when(
        () => mockStorage.delete(key: any(named: 'key')),
      ).thenAnswer((_) async {});

      await pinStorage.clearPin();

      verify(() => mockStorage.delete(key: 'pin_hash')).called(1);
      verify(() => mockStorage.delete(key: 'pin_salt')).called(1);
      verify(() => mockStorage.delete(key: 'pin_attempts')).called(1);
      verify(() => mockStorage.delete(key: 'pin_lockout_until')).called(1);
    });
  });
}
