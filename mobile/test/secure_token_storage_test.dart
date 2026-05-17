import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:mobile/core/storage/secure_token_storage.dart';

class MockSecureStorage extends Mock implements FlutterSecureStorage {}

void main() {
  group('SecureTokenStorage', () {
    late MockSecureStorage mockStorage;
    late SecureTokenStorage tokenStorage;

    setUp(() {
      mockStorage = MockSecureStorage();
      tokenStorage = SecureTokenStorage(secureStorage: mockStorage);
    });

    String _createJwt({String? userId, String? storeId}) {
      const header = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9';
      final payload = {
        'sub': userId ?? '550e8400-e29b-41d4-a716-446655440000',
        'exp':
            DateTime.now()
                .add(const Duration(hours: 1))
                .millisecondsSinceEpoch ~/
            1000,
        'type': 'access',
        if (storeId != null) 'store_id': storeId,
      };
      final payloadEncoded = base64Url
          .encode(utf8.encode(jsonEncode(payload)))
          .replaceAll('=', '');
      const signature = 'dummy_signature';
      return '$header.$payloadEncoded.$signature';
    }

    test('saveTokens stores access and refresh tokens', () async {
      const accessToken = 'access_token_test';
      const refreshToken = 'refresh_token_test';

      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});

      await tokenStorage.saveTokens(
        accessToken: accessToken,
        refreshToken: refreshToken,
      );

      verify(
        () => mockStorage.write(key: 'access_token', value: accessToken),
      ).called(1);
      verify(
        () => mockStorage.write(key: 'refresh_token', value: refreshToken),
      ).called(1);
    });

    test('saveTokens extracts and stores user_id from JWT', () async {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      const refreshToken = 'refresh_token_test';
      final accessToken = _createJwt(userId: userId);

      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});

      await tokenStorage.saveTokens(
        accessToken: accessToken,
        refreshToken: refreshToken,
      );

      verify(() => mockStorage.write(key: 'user_id', value: userId)).called(1);
    });

    test('saveTokens extracts and stores store_id from JWT', () async {
      const storeId = '660e8400-e29b-41d4-a716-446655440000';
      const refreshToken = 'refresh_token_test';
      final accessToken = _createJwt(storeId: storeId);

      when(
        () => mockStorage.write(
          key: any(named: 'key'),
          value: any(named: 'value'),
        ),
      ).thenAnswer((_) async {});

      await tokenStorage.saveTokens(
        accessToken: accessToken,
        refreshToken: refreshToken,
      );

      verify(
        () => mockStorage.write(key: 'store_id', value: storeId),
      ).called(1);
    });

    test('getAccessToken returns stored token', () async {
      const token = 'access_token_test';
      when(
        () => mockStorage.read(key: 'access_token'),
      ).thenAnswer((_) async => token);

      final result = await tokenStorage.getAccessToken();

      expect(result, token);
    });

    test('getRefreshToken returns stored token', () async {
      const token = 'refresh_token_test';
      when(
        () => mockStorage.read(key: 'refresh_token'),
      ).thenAnswer((_) async => token);

      final result = await tokenStorage.getRefreshToken();

      expect(result, token);
    });

    test('getUserId returns stored user ID', () async {
      const userId = '550e8400-e29b-41d4-a716-446655440000';
      when(
        () => mockStorage.read(key: 'user_id'),
      ).thenAnswer((_) async => userId);

      final result = await tokenStorage.getUserId();

      expect(result, userId);
    });

    test('getStoreId returns stored store ID', () async {
      const storeId = '660e8400-e29b-41d4-a716-446655440000';
      when(
        () => mockStorage.read(key: 'store_id'),
      ).thenAnswer((_) async => storeId);

      final result = await tokenStorage.getStoreId();

      expect(result, storeId);
    });

    test('clearTokens deletes all stored tokens and IDs', () async {
      when(
        () => mockStorage.delete(key: any(named: 'key')),
      ).thenAnswer((_) async {});

      await tokenStorage.clearTokens();

      verify(() => mockStorage.delete(key: 'access_token')).called(1);
      verify(() => mockStorage.delete(key: 'refresh_token')).called(1);
      verify(() => mockStorage.delete(key: 'user_id')).called(1);
      verify(() => mockStorage.delete(key: 'store_id')).called(1);
    });
  });
}
