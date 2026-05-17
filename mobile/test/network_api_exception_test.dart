import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_exception.dart';

void main() {
  group('parseException', () {
    test('connectionTimeout → ConnectionException', () {
      final dioException = DioException(
        requestOptions: RequestOptions(path: '/test'),
        type: DioExceptionType.connectionTimeout,
      );

      final result = parseException(dioException);

      expect(result, isA<ConnectionException>());
      expect(
        result.message,
        'Pas de connexion. Vos données sont sauvegardées localement.',
      );
    });

    test('receiveTimeout → ConnectionException', () {
      final dioException = DioException(
        requestOptions: RequestOptions(path: '/test'),
        type: DioExceptionType.receiveTimeout,
      );

      final result = parseException(dioException);

      expect(result, isA<ConnectionException>());
    });

    test('connectionError → ConnectionException', () {
      final dioException = DioException(
        requestOptions: RequestOptions(path: '/test'),
        type: DioExceptionType.connectionError,
      );

      final result = parseException(dioException);

      expect(result, isA<ConnectionException>());
    });

    test('null response → ConnectionException', () {
      final dioException = DioException(
        requestOptions: RequestOptions(path: '/test'),
        response: null,
      );

      final result = parseException(dioException);

      expect(result, isA<ConnectionException>());
    });

    test('401 with valid body → UnauthorizedException', () {
      final response = Response(
        data: {
          'code': 'INVALID_CREDENTIALS',
          'detail': 'Email ou mot de passe incorrect.',
          'field': null,
        },
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/auth/login'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<UnauthorizedException>());
      final ex = result as UnauthorizedException;
      expect(ex.statusCode, 401);
      expect(ex.code, 'INVALID_CREDENTIALS');
      expect(ex.message, 'Email ou mot de passe incorrect.');
      expect(ex.field, isNull);
    });

    test('401 with field error → UnauthorizedException with field', () {
      final response = Response(
        data: {
          'code': 'INVALID_EMAIL',
          'detail': 'Email invalide.',
          'field': 'email',
        },
        statusCode: 401,
        requestOptions: RequestOptions(path: '/api/v1/auth/login'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<UnauthorizedException>());
      final ex = result as UnauthorizedException;
      expect(ex.field, 'email');
    });

    test('409 with valid body → ConflictException', () {
      final response = Response(
        data: {
          'code': 'PRODUCT_ALREADY_EXISTS',
          'detail': 'Un produit avec ce code barre existe déjà.',
          'field': null,
        },
        statusCode: 409,
        requestOptions: RequestOptions(path: '/api/v1/products'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<ConflictException>());
      final ex = result as ConflictException;
      expect(ex.statusCode, 409);
      expect(ex.code, 'PRODUCT_ALREADY_EXISTS');
      expect(ex.message, 'Un produit avec ce code barre existe déjà.');
    });

    test('422 with valid body → ApiException', () {
      final response = Response(
        data: {
          'code': 'VALIDATION_ERROR',
          'detail': 'Données invalides.',
          'field': 'phone_number',
        },
        statusCode: 422,
        requestOptions: RequestOptions(path: '/api/v1/auth/register'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<ApiException>());
      expect(result, isNot(isA<UnauthorizedException>()));
      expect(result, isNot(isA<ConflictException>()));
      final ex = result as ApiException;
      expect(ex.statusCode, 422);
      expect(ex.code, 'VALIDATION_ERROR');
    });

    test('500 with malformed body → ApiException with fallback', () {
      final response = Response(
        data: null,
        statusCode: 500,
        requestOptions: RequestOptions(path: '/api/v1/sync'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<ApiException>());
      final ex = result as ApiException;
      expect(ex.statusCode, 500);
      expect(ex.code, 'UNKNOWN');
      expect(ex.message, 'Erreur serveur.');
    });

    test('500 with missing keys in body → ApiException with fallback', () {
      final response = Response(
        data: {'some_field': 'value'},
        statusCode: 500,
        requestOptions: RequestOptions(path: '/api/v1/sync'),
      );
      final dioException = DioException(
        requestOptions: response.requestOptions,
        response: response,
        type: DioExceptionType.badResponse,
      );

      final result = parseException(dioException);

      expect(result, isA<ApiException>());
      final ex = result as ApiException;
      expect(ex.code, 'UNKNOWN');
      expect(ex.message, 'Erreur serveur.');
    });
  });
}
