import 'dart:async';

import 'package:dio/dio.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../features/auth/data/datasources/auth_remote_datasource.dart';
import '../../features/auth/data/repositories/auth_repository_impl.dart';
import '../../features/auth/domain/repositories/auth_repository.dart';
import '../../features/sync/data/datasources/sync_remote_datasource.dart';
import '../storage/pin_storage.dart';
import '../storage/secure_token_storage.dart';
import 'dio_client.dart';
import 'token_storage.dart';

part 'network_providers.g.dart';

/// Provides the TokenStorage implementation.
/// Must be overridden in ProviderScope before use.
@Riverpod(keepAlive: true)
TokenStorage tokenStorage(Ref ref) {
  throw UnimplementedError(
    'Override tokenStorageProvider with SecureTokenStorage implementation',
  );
}

/// Broadcasts void event when authentication expires (session invalid).
/// Auth layer listens to this stream and routes to login screen.
@Riverpod(keepAlive: true)
Raw<StreamController<void>> authExpiredController(Ref ref) {
  final controller = StreamController<void>.broadcast();
  ref.onDispose(controller.close);
  return controller;
}

/// Provides a configured Dio instance with JWT auth, refresh, and error handling.
@Riverpod(keepAlive: true)
Dio dio(Ref ref) {
  final storage = ref.watch(tokenStorageProvider);
  // ignore: close_sinks
  final controller = ref.watch(authExpiredControllerProvider);

  return buildDio(
    tokenStorage: storage,
    onAuthExpired: () => controller.add(null),
  );
}

/// Provides the concrete SecureTokenStorage implementation.
@Riverpod(keepAlive: true)
SecureTokenStorage secureTokenStorage(Ref ref) {
  return SecureTokenStorage();
}

/// Provides PIN storage for local PIN management.
@Riverpod(keepAlive: true)
PinStorage pinStorage(Ref ref) {
  return PinStorage();
}

/// Provides the remote data source for auth API calls.
@Riverpod(keepAlive: true)
AuthRemoteDataSource authRemoteDataSource(Ref ref) {
  final dio = ref.watch(dioProvider);
  return AuthRemoteDataSource(dio);
}

/// Provides the auth repository implementation.
@Riverpod(keepAlive: true)
AuthRepository authRepository(Ref ref) {
  final dataSource = ref.watch(authRemoteDataSourceProvider);
  final tokenStorage = ref.watch(secureTokenStorageProvider);
  final pinStorage = ref.watch(pinStorageProvider);

  return AuthRepositoryImpl(
    dataSource: dataSource,
    tokenStorage: tokenStorage,
    pinStorage: pinStorage,
  );
}

/// Provides the sync remote data source for sync operations.
@Riverpod(keepAlive: true)
SyncRemoteDataSource syncRemoteDataSource(Ref ref) {
  final dio = ref.watch(dioProvider);
  return SyncRemoteDataSource(dio);
}
