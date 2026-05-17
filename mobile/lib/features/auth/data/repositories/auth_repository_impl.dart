import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import '../../../../core/network/api_exception.dart';
import '../../../../core/storage/pin_storage.dart';
import '../../../../core/storage/secure_token_storage.dart';
import '../../domain/entities/user.dart';
import '../../domain/repositories/auth_repository.dart';
import '../datasources/auth_remote_datasource.dart';
import '../models/auth_models.dart';

/// Concrete implementation of [AuthRepository].
class AuthRepositoryImpl implements AuthRepository {
  /// Creates an AuthRepositoryImpl.
  AuthRepositoryImpl({
    required this.dataSource,
    required this.tokenStorage,
    required this.pinStorage,
  });

  /// Remote data source.
  final AuthRemoteDataSource dataSource;

  /// Secure token storage.
  final SecureTokenStorage tokenStorage;

  /// PIN storage.
  final PinStorage pinStorage;

  @override
  Future<User> register({
    required String email,
    required String password,
    required String phoneNumber,
  }) async {
    try {
      // Register account.
      final registerRes = await dataSource.register(
        RegisterRequestDto(
          email: email,
          password: password,
          phoneNumber: phoneNumber,
        ),
      );

      // Auto-login after registration.
      final tokenRes = await dataSource.login(
        LoginRequestDto(email: email, password: password),
      );

      // Store tokens.
      await tokenStorage.saveTokens(
        accessToken: tokenRes.accessToken,
        refreshToken: tokenRes.refreshToken,
      );

      // Return user constructed from JWT claims.
      final userId = await tokenStorage.getUserId();
      return User(
        id: userId ?? registerRes.userId,
        email: email,
        phoneNumber: phoneNumber,
        storeId: await tokenStorage.getStoreId(),
      );
    } on DioException catch (e) {
      throw _parseException(e);
    }
  }

  @override
  Future<User> login({required String email, required String password}) async {
    try {
      final tokenRes = await dataSource.login(
        LoginRequestDto(email: email, password: password),
      );

      await tokenStorage.saveTokens(
        accessToken: tokenRes.accessToken,
        refreshToken: tokenRes.refreshToken,
      );

      final userId = await tokenStorage.getUserId();
      return User(
        id: userId ?? const Uuid().v4(),
        email: email,
        phoneNumber: '',
        storeId: await tokenStorage.getStoreId(),
      );
    } on DioException catch (e) {
      throw _parseException(e);
    }
  }

  @override
  Future<void> setupPin(String pin) async {
    await pinStorage.savePinHash(pin);
  }

  @override
  Future<bool> verifyPin(String pin) async {
    try {
      return await pinStorage.verifyPin(pin);
    } on PinLockedException catch (e) {
      throw Exception(e.toString());
    }
  }

  @override
  Future<int> getPinAttempts() => pinStorage.getPinAttempts();

  @override
  Future<void> resetPinAttempts() => pinStorage.resetAttempts();

  @override
  Future<void> sendPasswordReset(String email) async {
    try {
      await dataSource.forgotPassword(ForgotPasswordRequestDto(email: email));
    } on DioException catch (e) {
      throw _parseException(e);
    }
  }

  @override
  Future<void> logout() async {
    await tokenStorage.clearTokens();
    await pinStorage.clearPin();
  }

  @override
  Future<User?> getCurrentUser() async {
    final userId = await tokenStorage.getUserId();
    if (userId == null) return null;

    // Note: in a full implementation, we'd fetch additional user details
    // from GET /api/v1/auth/me. For now, return user with basic info.
    return User(
      id: userId,
      email: '', // Not available in token; would need API call.
      phoneNumber: '',
      storeId: await tokenStorage.getStoreId(),
    );
  }

  @override
  Future<bool> hasPinSetup() => pinStorage.hasPinConfigured();

  /// Converts [DioException] to a [NetworkException].
  NetworkException _parseException(DioException e) {
    return parseException(e);
  }
}
