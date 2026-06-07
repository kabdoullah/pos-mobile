import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../network/token_storage.dart';

/// Storage keys for JWT tokens in secure storage.
abstract class _TokenStorageKeys {
  /// Access token (short-lived JWT).
  static const String accessToken = 'access_token';

  /// Refresh token (long-lived JWT).
  static const String refreshToken = 'refresh_token';

  /// User ID extracted from JWT payload.
  static const String userId = 'user_id';

  /// Store ID extracted from JWT payload.
  static const String storeId = 'store_id';

  /// User phone number saved at login time (primary identifier).
  static const String phoneNumber = 'phone_number';
}

/// Concrete implementation of TokenStorage using flutter_secure_storage.
/// Also extracts and stores user_id and store_id from the JWT payload.
class SecureTokenStorage implements TokenStorage {
  /// Creates a SecureTokenStorage instance.
  SecureTokenStorage({FlutterSecureStorage? secureStorage})
    : _storage = secureStorage ?? const FlutterSecureStorage();

  /// Underlying secure storage backend.
  final FlutterSecureStorage _storage;

  @override
  Future<String?> getAccessToken() =>
      _storage.read(key: _TokenStorageKeys.accessToken);

  @override
  Future<String?> getRefreshToken() =>
      _storage.read(key: _TokenStorageKeys.refreshToken);

  @override
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    // Extract user_id and store_id from access token payload.
    final (userId: userId, storeId: storeId) = _extractClaimsFromJwt(
      accessToken,
    );

    await Future.wait([
      _storage.write(key: _TokenStorageKeys.accessToken, value: accessToken),
      _storage.write(key: _TokenStorageKeys.refreshToken, value: refreshToken),
      if (userId != null)
        _storage.write(key: _TokenStorageKeys.userId, value: userId),
      if (storeId != null)
        _storage.write(key: _TokenStorageKeys.storeId, value: storeId),
    ]);
  }

  @override
  Future<void> clearTokens() => Future.wait([
    _storage.delete(key: _TokenStorageKeys.accessToken),
    _storage.delete(key: _TokenStorageKeys.refreshToken),
    _storage.delete(key: _TokenStorageKeys.userId),
    _storage.delete(key: _TokenStorageKeys.storeId),
    _storage.delete(key: _TokenStorageKeys.phoneNumber),
    // Legacy key cleanup for users who had email stored before phone-first migration.
    _storage.delete(key: 'email'),
  ]);

  /// Retrieves the stored user ID.
  Future<String?> getUserId() => _storage.read(key: _TokenStorageKeys.userId);

  /// Retrieves the stored store ID.
  Future<String?> getStoreId() => _storage.read(key: _TokenStorageKeys.storeId);

  /// Saves the user phone number (called after successful login/registration).
  Future<void> savePhone(String phoneNumber) =>
      _storage.write(key: _TokenStorageKeys.phoneNumber, value: phoneNumber);

  /// Retrieves the stored user phone number.
  Future<String?> getPhone() =>
      _storage.read(key: _TokenStorageKeys.phoneNumber);

  /// Extracts user_id (sub) and store_id from a JWT access token.
  /// Does NOT verify the signature (server responsibility).
  ({String? userId, String? storeId}) _extractClaimsFromJwt(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return (userId: null, storeId: null);

      // Decode the payload (middle part).
      final payload = parts[1];
      // Add padding if necessary (base64url may omit trailing =).
      final padded = payload.padRight((payload.length + 3) ~/ 4 * 4, '=');

      final decoded = utf8.decode(base64Url.decode(padded));
      final json = jsonDecode(decoded) as Map<String, dynamic>;

      return (
        userId: json['sub'] as String?,
        storeId: json['store_id'] as String?,
      );
    } catch (_) {
      return (userId: null, storeId: null);
    }
  }
}
