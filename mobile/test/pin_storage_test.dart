import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:mobile/core/storage/pin_storage.dart';

class MockSecureStorage extends Mock implements FlutterSecureStorage {}

/// In-memory [FlutterSecureStorage] for round-trip hashing tests.
class InMemorySecureStorage extends Fake implements FlutterSecureStorage {
  final Map<String, String> _data = {};

  @override
  Future<void> write({
    required String key,
    required String? value,
    // ignore: avoid_annotating_with_dynamic
    iOptions,
    aOptions,
    lOptions,
    webOptions,
    mOptions,
    wOptions,
  }) async {
    if (value == null) {
      _data.remove(key);
    } else {
      _data[key] = value;
    }
  }

  @override
  Future<String?> read({
    required String key,
    iOptions,
    aOptions,
    lOptions,
    webOptions,
    mOptions,
    wOptions,
  }) async => _data[key];

  @override
  Future<void> delete({
    required String key,
    iOptions,
    aOptions,
    lOptions,
    webOptions,
    mOptions,
    wOptions,
  }) async => _data.remove(key);
}

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

    test('hasPinConfigured returns true for current-format hash', () async {
      when(
        () => mockStorage.read(key: 'pin_hash'),
      ).thenAnswer((_) async => 'pbkdf2_sha256\$150000\$deadbeef');

      final result = await pinStorage.hasPinConfigured();

      expect(result, isTrue);
    });

    test('hasPinConfigured clears legacy hash and returns false', () async {
      when(
        () => mockStorage.read(key: 'pin_hash'),
      ).thenAnswer((_) async => 'legacy_sha256_hash');
      when(
        () => mockStorage.delete(key: any(named: 'key')),
      ).thenAnswer((_) async {});

      final result = await pinStorage.hasPinConfigured();

      expect(result, isFalse);
      verify(() => mockStorage.delete(key: 'pin_hash')).called(1);
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

  group('PinStorage PBKDF2 round-trip', () {
    late InMemorySecureStorage storage;
    late PinStorage pinStorage;

    setUp(() {
      storage = InMemorySecureStorage();
      pinStorage = PinStorage(
        secureStorage: storage,
        lockoutDuration: const Duration(seconds: 5),
      );
    });

    test('verifyPin succeeds for the saved PIN', () async {
      await pinStorage.savePinHash('1234');
      expect(await pinStorage.verifyPin('1234'), isTrue);
    });

    test('verifyPin fails for a wrong PIN', () async {
      await pinStorage.savePinHash('1234');
      expect(await pinStorage.verifyPin('0000'), isFalse);
    });

    test('stored hash uses the pbkdf2_sha256 format', () async {
      await pinStorage.savePinHash('1234');
      final hash = await storage.read(key: 'pin_hash');
      expect(hash, startsWith('pbkdf2_sha256\$150000\$'));
    });

    test('salt is cryptographically random across saves', () async {
      await pinStorage.savePinHash('1234');
      final salt1 = await storage.read(key: 'pin_salt');
      await pinStorage.savePinHash('1234');
      final salt2 = await storage.read(key: 'pin_salt');

      expect(salt1, isNotNull);
      expect(salt1!.length, 64); // 32 bytes as hex
      expect(salt1, isNot(equals(salt2)));
    });

    test('lockout triggers after max failed attempts', () async {
      await pinStorage.savePinHash('1234');
      for (var i = 0; i < PinStorage.maxAttempts; i++) {
        await pinStorage.verifyPin('0000');
      }
      expect(
        () => pinStorage.verifyPin('1234'),
        throwsA(isA<PinLockedException>()),
      );
    });
  });
}
