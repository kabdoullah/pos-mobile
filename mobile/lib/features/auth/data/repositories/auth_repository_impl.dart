import 'package:dio/dio.dart';

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
    required String phoneNumber,
    required String password,
    String? email,
  }) async {
    try {
      final registerRes = await dataSource.register(
        RegisterRequestDto(
          phoneNumber: phoneNumber,
          password: password,
          email: email,
        ),
      );

      // Auto-login after registration.
      final tokenRes = await dataSource.login(
        LoginRequestDto(phoneNumber: phoneNumber, password: password),
      );

      await tokenStorage.saveTokens(
        accessToken: tokenRes.accessToken,
        refreshToken: tokenRes.refreshToken,
      );
      await tokenStorage.savePhone(phoneNumber);

      final userId = await tokenStorage.getUserId();
      return User(
        id: userId ?? registerRes.userId,
        phoneNumber: phoneNumber,
        email: email,
        storeId: await tokenStorage.getStoreId(),
      );
    } on DioException catch (e) {
      throw _parseException(e);
    }
  }

  @override
  Future<User> login({
    required String phoneNumber,
    required String password,
  }) async {
    try {
      final tokenRes = await dataSource.login(
        LoginRequestDto(phoneNumber: phoneNumber, password: password),
      );

      await tokenStorage.saveTokens(
        accessToken: tokenRes.accessToken,
        refreshToken: tokenRes.refreshToken,
      );
      await tokenStorage.savePhone(phoneNumber);

      final userId = await tokenStorage.getUserId();
      if (userId == null) {
        throw Exception('Login failed: user ID missing from token');
      }
      return User(
        id: userId,
        phoneNumber: phoneNumber,
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

    return User(
      id: userId,
      phoneNumber: await tokenStorage.getPhone() ?? '',
      storeId: await tokenStorage.getStoreId(),
    );
  }

  @override
  Future<bool> hasPinSetup() => pinStorage.hasPinConfigured();

  @override
  Future<void> refreshTokens() async {
    final refreshToken = await tokenStorage.getRefreshToken();
    if (refreshToken == null) return;
    try {
      final tokenRes = await dataSource.refresh(
        RefreshRequestDto(refreshToken: refreshToken),
      );
      await tokenStorage.saveTokens(
        accessToken: tokenRes.accessToken,
        refreshToken: tokenRes.refreshToken,
      );
    } on DioException catch (e) {
      throw _parseException(e);
    }
  }

  /// Converts [DioException] to a [NetworkException].
  NetworkException _parseException(DioException e) {
    return parseException(e);
  }
}
