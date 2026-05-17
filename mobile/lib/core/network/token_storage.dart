/// Abstraction for secure token persistence (JWT tokens).
/// Implementation (SecureTokenStorage) deferred to next phase.
abstract interface class TokenStorage {
  /// Retrieves the access token from secure storage, or null if not found.
  Future<String?> getAccessToken();

  /// Retrieves the refresh token from secure storage, or null if not found.
  Future<String?> getRefreshToken();

  /// Persists both access and refresh tokens to secure storage.
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  });

  /// Clears all stored tokens (logout).
  Future<void> clearTokens();
}
