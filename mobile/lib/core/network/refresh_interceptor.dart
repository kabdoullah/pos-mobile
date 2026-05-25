import 'dart:async';

import 'package:dio/dio.dart';
import 'package:logger/logger.dart';

import 'api_exception.dart';
import 'token_storage.dart';

/// Handles 401 responses by refreshing the token and retrying the request.
/// Prevents concurrent refresh calls using a Completer-based lock.
class RefreshInterceptor extends Interceptor {
  /// Creates a RefreshInterceptor.
  RefreshInterceptor({
    required this.tokenStorage,
    required this.refreshCall,
    required this.onAuthExpired,
    required this.dio,
  });

  /// Handles secure token persistence.
  final TokenStorage tokenStorage;

  /// Function to call POST /api/v1/auth/refresh with refresh token.
  /// Returns new (accessToken, refreshToken) pair.
  final Future<({String accessToken, String refreshToken})> Function(
    String refreshToken,
  )
  refreshCall;

  /// Called when refresh fails (token expired). Triggers logout redirect.
  final void Function() onAuthExpired;

  /// Dio instance for retrying the original request after token refresh.
  final Dio dio;

  static final _logger = Logger();

  /// Ensures only one refresh attempt at a time.
  bool _isRefreshing = false;

  /// Completer for waiters of the current refresh attempt.
  Completer<bool>? _refreshCompleter;

  static const _publicPaths = {
    '/api/v1/auth/register',
    '/api/v1/auth/login',
    '/api/v1/auth/forgot-password',
    '/api/v1/auth/reset-password',
    '/health',
  };

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode != 401) {
      handler.next(err);
      return;
    }

    // Don't refresh tokens for public endpoints.
    if (_isPublicPath(err.requestOptions.path)) {
      handler.next(err);
      return;
    }

    // If already refreshing, wait for the result.
    if (_isRefreshing) {
      final success = await _refreshCompleter!.future;
      if (success) {
        // Retry original request with new token (in practice, re-enters onRequest).
        handler.resolve(
          Response(
            data: null,
            statusCode: 200,
            requestOptions: err.requestOptions,
          ),
        );
      } else {
        // Refresh failed; forward error.
        handler.next(err);
      }
      return;
    }

    // Begin refresh.
    _isRefreshing = true;
    _refreshCompleter = Completer<bool>();

    try {
      final refreshToken = await tokenStorage.getRefreshToken();
      if (refreshToken == null) {
        throw UnauthorizedException(
          code: 'NO_REFRESH_TOKEN',
          detail: 'Session expirée. Veuillez vous reconnecter.',
        );
      }

      final result = await refreshCall(refreshToken);

      await tokenStorage.saveTokens(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
      );

      _refreshCompleter!.complete(true);
      // Retry the original request with the new token.
      // The request re-enters onRequest() which adds the new token to headers.
      handler.resolve(await dio.fetch(err.requestOptions));
    } catch (e) {
      _logger.e('Token refresh failed: $e');
      _refreshCompleter!.complete(false);
      onAuthExpired();

      handler.next(
        DioException(
          requestOptions: err.requestOptions,
          error: e,
          type: DioExceptionType.unknown,
        ),
      );
    } finally {
      _isRefreshing = false;
      _refreshCompleter = null;
    }
  }

  bool _isPublicPath(String path) => _publicPaths.contains(path);
}
