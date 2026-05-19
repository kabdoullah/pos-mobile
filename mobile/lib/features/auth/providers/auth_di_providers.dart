import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/network_providers.dart';
import '../data/datasources/auth_remote_datasource.dart';
import '../data/repositories/auth_repository_impl.dart';
import '../domain/repositories/auth_repository.dart';

part 'auth_di_providers.g.dart';

/// Provides the remote data source for auth API calls.
@riverpod
AuthRemoteDataSource authRemoteDataSource(Ref ref) {
  final dio = ref.watch(dioProvider);
  return AuthRemoteDataSource(dio);
}

/// Provides the auth repository implementation.
@riverpod
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
