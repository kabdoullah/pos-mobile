import 'dart:developer' as developer;

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../config.dart';
import 'api_exception.dart';
import 'auth_interceptor.dart';
import 'refresh_interceptor.dart';
import 'token_storage.dart';

/// Builds and configures a Dio instance with JWT auth, refresh, and error handling.
Dio buildDio({
  required TokenStorage tokenStorage,
  required void Function() onAuthExpired,
}) {
  // Dedicated Dio for refresh calls (no interceptors to prevent infinite loops).
  final refreshDio = Dio(
    BaseOptions(
      baseUrl: AppConfig.apiUrl,
      connectTimeout: const Duration(seconds: AppConfig.httpTimeoutSeconds),
      receiveTimeout: const Duration(seconds: AppConfig.httpTimeoutSeconds),
      contentType: 'application/json',
      validateStatus: null,
    ),
  );

  // Refresh call: POST /api/v1/auth/refresh
  Future<({String accessToken, String refreshToken})> refreshCall(
    String refreshToken,
  ) async {
    final response = await refreshDio.post<Map<String, dynamic>>(
      '/api/v1/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    if (response.statusCode != 200) {
      throw parseException(
        DioException(
          requestOptions: response.requestOptions,
          response: response,
          type: DioExceptionType.badResponse,
        ),
      );
    }

    final data = response.data;
    if (data == null) {
      throw ApiException(
        statusCode: 500,
        code: 'INVALID_REFRESH_RESPONSE',
        detail: 'Réponse serveur invalide.',
      );
    }

    return (
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String,
    );
  }

  // Main Dio instance.
  final dio = Dio(
    BaseOptions(
      baseUrl: AppConfig.apiUrl,
      connectTimeout: const Duration(seconds: AppConfig.httpTimeoutSeconds),
      receiveTimeout: const Duration(seconds: AppConfig.httpTimeoutSeconds),
      contentType: 'application/json',
      validateStatus: (status) =>
          status != null && status >= 200 && status < 300,
    ),
  );

  // Add interceptors.
  dio.interceptors.add(AuthInterceptor(tokenStorage: tokenStorage));
  dio.interceptors.add(
    RefreshInterceptor(
      tokenStorage: tokenStorage,
      refreshCall: refreshCall,
      onAuthExpired: onAuthExpired,
      dio: dio,
    ),
  );

  // Debug logging in dev.
  if (kDebugMode) {
    dio.interceptors.add(
      LogInterceptor(
        requestBody: false,
        responseBody: true,
        responseHeader: false,
        logPrint: (obj) {
          developer.log(obj.toString(), name: 'Dio');
        },
      ),
    );
  }

  return dio;
}
