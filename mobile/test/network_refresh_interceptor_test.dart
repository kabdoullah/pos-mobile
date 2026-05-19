import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_exception.dart';
import 'package:mobile/core/network/refresh_interceptor.dart';
import 'package:mobile/core/network/token_storage.dart';
import 'package:mocktail/mocktail.dart';

// ignore: unnecessary_lambdas
class MockTokenStorage extends Mock implements TokenStorage {}

void main() {
  group('RefreshInterceptor', () {
    test('single 401 → calls refreshCall once, new tokens saved', () async {
      final tokenStorage = MockTokenStorage();
      var refreshCallCount = 0;

      when(
        tokenStorage.getRefreshToken,
      ).thenAnswer((_) async => 'old_refresh_token');
      when(
        () => tokenStorage.saveTokens(
          accessToken: any(named: 'accessToken'),
          refreshToken: any(named: 'refreshToken'),
        ),
      ).thenAnswer((_) async {});

      Future<({String accessToken, String refreshToken})> refreshCall(
        String refreshToken,
      ) async {
        refreshCallCount++;
        return (accessToken: 'new_access', refreshToken: 'new_refresh');
      }

      var onAuthExpiredCalled = false;

      final interceptor = RefreshInterceptor(
        tokenStorage: tokenStorage,
        refreshCall: refreshCall,
        onAuthExpired: () => onAuthExpiredCalled = true,
      );

      // Simulate a 401 response.
      final errorResponse = Response(
        data: {'code': 'TOKEN_EXPIRED', 'detail': 'Token expired.'},
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/products'),
      );
      final dioException = DioException(
        requestOptions: errorResponse.requestOptions,
        response: errorResponse,
        type: DioExceptionType.badResponse,
      );

      // Create handler and intercept.
      final handler = _TestErrorInterceptorHandler();
      await interceptor.onError(dioException, handler);

      // Verify refresh was called once.
      expect(refreshCallCount, 1);

      // Verify auth expired was NOT called.
      expect(onAuthExpiredCalled, false);

      // Verify new tokens were saved.
      verify(
        () => tokenStorage.saveTokens(
          accessToken: 'new_access',
          refreshToken: 'new_refresh',
        ),
      ).called(1);

      // Verify response was resolved (not errored).
      expect(handler.resolvedResponse, isNotNull);
      expect(handler.erroredError, isNull);
    });

    test('refresh fails → calls onAuthExpired, forwards error', () async {
      final tokenStorage = MockTokenStorage();
      var refreshCallCount = 0;

      when(
        tokenStorage.getRefreshToken,
      ).thenAnswer((_) async => 'expired_refresh_token');

      Future<({String accessToken, String refreshToken})> refreshCall(
        String refreshToken,
      ) async {
        refreshCallCount++;
        throw ApiException(
          statusCode: 401,
          code: 'REFRESH_TOKEN_EXPIRED',
          detail: 'Refresh token expired.',
        );
      }

      var onAuthExpiredCalled = false;

      final interceptor = RefreshInterceptor(
        tokenStorage: tokenStorage,
        refreshCall: refreshCall,
        onAuthExpired: () => onAuthExpiredCalled = true,
      );

      final errorResponse = Response(
        data: {'code': 'TOKEN_EXPIRED', 'detail': 'Token expired.'},
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/products'),
      );
      final dioException = DioException(
        requestOptions: errorResponse.requestOptions,
        response: errorResponse,
        type: DioExceptionType.badResponse,
      );

      final handler = _TestErrorInterceptorHandler();
      await interceptor.onError(dioException, handler);

      // Verify refresh was attempted once.
      expect(refreshCallCount, 1);

      // Verify onAuthExpired was called.
      expect(onAuthExpiredCalled, true);

      // Verify error was forwarded.
      expect(handler.erroredError, isNotNull);
      expect(handler.resolvedResponse, isNull);
    });

    test('concurrent 401s → refreshCall invoked only once', () async {
      final tokenStorage = MockTokenStorage();
      var refreshCallCount = 0;
      final refreshCompleter = Completer<void>();

      when(
        tokenStorage.getRefreshToken,
      ).thenAnswer((_) async => 'refresh_token');
      when(
        () => tokenStorage.saveTokens(
          accessToken: any(named: 'accessToken'),
          refreshToken: any(named: 'refreshToken'),
        ),
      ).thenAnswer((_) async {});

      Future<({String accessToken, String refreshToken})> refreshCall(
        String refreshToken,
      ) async {
        refreshCallCount++;
        // Block until the test signals completion.
        await refreshCompleter.future;
        return (accessToken: 'new_access', refreshToken: 'new_refresh');
      }

      var onAuthExpiredCallCount = 0;

      final interceptor = RefreshInterceptor(
        tokenStorage: tokenStorage,
        refreshCall: refreshCall,
        onAuthExpired: () => onAuthExpiredCallCount++,
      );

      // Create 3 concurrent 401 errors.
      final errorResponse = Response(
        data: {'code': 'TOKEN_EXPIRED', 'detail': 'Token expired.'},
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/products'),
      );

      final handlers = <_TestErrorInterceptorHandler>[];
      final futures = <Future<void>>[];

      for (var i = 0; i < 3; i++) {
        final dioException = DioException(
          requestOptions: errorResponse.requestOptions,
          response: errorResponse,
          type: DioExceptionType.badResponse,
        );

        final handler = _TestErrorInterceptorHandler();
        handlers.add(handler);

        futures.add(interceptor.onError(dioException, handler));
      }

      // Yield to allow tasks to start.
      await Future<void>.delayed(Duration.zero);

      // At this point, all 3 should be waiting on the refresh.
      expect(refreshCallCount, 1);

      // Unblock the refresh.
      refreshCompleter.complete();

      // Wait for all handlers to finish.
      await Future.wait(futures);

      // Verify refresh was still called only once (the lock worked).
      expect(refreshCallCount, 1);

      // Verify onAuthExpired was NOT called (refresh succeeded).
      expect(onAuthExpiredCallCount, 0);

      // Verify all handlers either resolved or errored.
      for (final handler in handlers) {
        final hasResult =
            handler.resolvedResponse != null || handler.erroredError != null;
        expect(
          hasResult,
          true,
          reason: 'Handler should have resolved or errored',
        );
      }
    });

    test(
      'no refresh token available → calls onAuthExpired immediately',
      () async {
        final tokenStorage = MockTokenStorage();

        when(tokenStorage.getRefreshToken).thenAnswer((_) async => null);

        var onAuthExpiredCalled = false;

        final interceptor = RefreshInterceptor(
          tokenStorage: tokenStorage,
          refreshCall: (_) async => throw Exception('should not be called'),
          onAuthExpired: () => onAuthExpiredCalled = true,
        );

        final errorResponse = Response(
          data: {'code': 'TOKEN_EXPIRED', 'detail': 'Token expired.'},
          statusCode: 401,
          requestOptions: RequestOptions(path: '/api/v1/products'),
        );
        final dioException = DioException(
          requestOptions: errorResponse.requestOptions,
          response: errorResponse,
          type: DioExceptionType.badResponse,
        );

        final handler = _TestErrorInterceptorHandler();
        await interceptor.onError(dioException, handler);

        // Verify onAuthExpired was called.
        expect(onAuthExpiredCalled, true);

        // Verify error was forwarded.
        expect(handler.erroredError, isNotNull);
      },
    );

    test('non-401 error → passed through unchanged', () async {
      final tokenStorage = MockTokenStorage();

      var onAuthExpiredCalled = false;

      final interceptor = RefreshInterceptor(
        tokenStorage: tokenStorage,
        refreshCall: (_) async => throw Exception('should not be called'),
        onAuthExpired: () => onAuthExpiredCalled = true,
      );

      final errorResponse = Response(
        data: {'code': 'VALIDATION_ERROR', 'detail': 'Invalid data.'},
        statusCode: 422,
        requestOptions: RequestOptions(path: '/api/v1/products'),
      );
      final dioException = DioException(
        requestOptions: errorResponse.requestOptions,
        response: errorResponse,
        type: DioExceptionType.badResponse,
      );

      final handler = _TestErrorInterceptorHandler();
      await interceptor.onError(dioException, handler);

      // Verify onAuthExpired was NOT called.
      expect(onAuthExpiredCalled, false);

      // Verify error was forwarded as-is (not resolved).
      expect(handler.erroredError, dioException);
      expect(handler.resolvedResponse, isNull);
    });
  });
}

/// Test double for ErrorInterceptorHandler to track resolve/error calls.
class _TestErrorInterceptorHandler extends ErrorInterceptorHandler {
  Response<dynamic>? resolvedResponse;
  DioException? erroredError;

  @override
  void resolve(Response<dynamic> response) => resolvedResponse = response;

  @override
  void next(DioException err) => erroredError = err;
}
