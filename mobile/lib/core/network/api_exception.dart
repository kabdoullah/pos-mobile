import 'package:dio/dio.dart';

/// Base exception for all network-related errors.
sealed class NetworkException implements Exception {
  /// Creates a NetworkException with a user-facing message.
  NetworkException(this.message);

  /// User-facing message in French.
  final String message;
}

/// No connection, timeout, or network unreachable.
/// User-facing message is in French.
class ConnectionException extends NetworkException {
  /// Creates a ConnectionException.
  ConnectionException()
    : super('Pas de connexion. Vos données sont sauvegardées localement.');
}

/// API returned 4xx or 5xx with structured error body.
/// Provides machine-readable error code, user-facing message, and optional field.
class ApiException extends NetworkException {
  /// Creates an ApiException.
  ApiException({
    required this.statusCode,
    required this.code,
    required String detail,
    this.field,
  }) : super(detail);

  /// HTTP status code (400–599).
  final int statusCode;

  /// Machine-readable error code (e.g., 'INVALID_EMAIL').
  final String code;

  /// Optional field name if validation error.
  final String? field;
}

/// 401 Unauthorized — token invalid or expired, refresh failed.
/// Extends ApiException to preserve HTTP status and error code.
class UnauthorizedException extends ApiException {
  /// Creates an UnauthorizedException.
  UnauthorizedException({
    required super.code,
    required super.detail,
    super.field,
  }) : super(statusCode: 401);
}

/// 409 Conflict — sync or unique constraint violation.
/// Extends ApiException to preserve HTTP status and error code.
class ConflictException extends ApiException {
  /// Creates a ConflictException.
  ConflictException({required super.code, required super.detail, super.field})
    : super(statusCode: 409);
}

/// Parses DioException into a project-specific NetworkException.
NetworkException parseException(DioException e) {
  // Network errors (no response received).
  if (e.type == DioExceptionType.connectionTimeout ||
      e.type == DioExceptionType.receiveTimeout ||
      e.type == DioExceptionType.connectionError ||
      e.response == null) {
    return ConnectionException();
  }

  final statusCode = e.response!.statusCode ?? 500;
  final (code: code, detail: detail, field: field) = _parseBody(
    e.response!.data as Map<String, dynamic>?,
  );

  // Specific status codes.
  if (statusCode == 401) {
    return UnauthorizedException(code: code, detail: detail, field: field);
  }
  if (statusCode == 409) {
    return ConflictException(code: code, detail: detail, field: field);
  }

  // Generic 4xx/5xx.
  return ApiException(
    statusCode: statusCode,
    code: code,
    detail: detail,
    field: field,
  );
}

({String code, String detail, String? field}) _parseBody(
  Map<String, dynamic>? data,
) {
  if (data == null) {
    return (code: 'UNKNOWN', detail: 'Erreur serveur.', field: null);
  }

  final code = (data['code'] as String?) ?? 'UNKNOWN';
  final detail = (data['detail'] as String?) ?? 'Erreur serveur.';
  final field = data['field'] as String?;

  return (code: code, detail: detail, field: field);
}
