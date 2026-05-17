import 'package:dio/dio.dart';

import 'token_storage.dart';

/// Injects Bearer token into request headers for authenticated endpoints.
class AuthInterceptor extends Interceptor {
  /// Creates an AuthInterceptor.
  AuthInterceptor({required this.tokenStorage});

  /// Handles secure token retrieval.
  final TokenStorage tokenStorage;

  static const _publicPaths = {
    '/api/v1/auth/register',
    '/api/v1/auth/login',
    '/api/v1/auth/forgot-password',
    '/api/v1/auth/reset-password',
    '/health',
  }; // Routes that don't require authentication

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (_isPublicPath(options.path)) {
      handler.next(options);
      return;
    }

    final token = await tokenStorage.getAccessToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }

    handler.next(options);
  }

  bool _isPublicPath(String path) => _publicPaths.contains(path);
}
