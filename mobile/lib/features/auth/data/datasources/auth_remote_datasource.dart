import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';

import '../models/auth_models.dart';

part 'auth_remote_datasource.g.dart';

/// Remote data source for authentication via HTTP API.
@RestApi()
abstract class AuthRemoteDataSource {
  /// Creates an AuthRemoteDataSource instance.
  factory AuthRemoteDataSource(Dio dio, {String baseUrl}) =
      _AuthRemoteDataSource;

  /// Registers a new user account.
  /// Endpoint: POST /api/v1/auth/register
  @POST('/api/v1/auth/register')
  Future<RegisterResponseDto> register(@Body() RegisterRequestDto request);

  /// Logs in with email and password.
  /// Endpoint: POST /api/v1/auth/login
  @POST('/api/v1/auth/login')
  Future<TokenResponseDto> login(@Body() LoginRequestDto request);

  /// Requests a password reset email.
  /// Endpoint: POST /api/v1/auth/forgot-password
  @POST('/api/v1/auth/forgot-password')
  Future<void> forgotPassword(@Body() ForgotPasswordRequestDto request);

  /// Confirms a password reset.
  /// Endpoint: POST /api/v1/auth/reset-password
  @POST('/api/v1/auth/reset-password')
  Future<void> resetPassword(@Body() ResetPasswordRequestDto request);

  /// Refreshes the access token using the refresh token.
  /// Endpoint: POST /api/v1/auth/refresh
  @POST('/api/v1/auth/refresh')
  Future<TokenResponseDto> refresh(@Body() RefreshRequestDto request);
}
