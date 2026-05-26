import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../core/network/network_providers.dart';
import '../data/datasources/auth_remote_datasource.dart';
import '../data/repositories/auth_repository_impl.dart';
import '../domain/repositories/auth_repository.dart';

part 'auth_di_providers.g.dart';

/// Provides the remote data source for auth API calls.
@riverpod
AuthRemoteDataSource authRemoteDataSource(Ref ref) {
  return AuthRemoteDataSource(ref.read(dioProvider));
}

/// Provides the auth repository implementation.
@riverpod
AuthRepository authRepository(Ref ref) {
  return AuthRepositoryImpl(
    dataSource: ref.read(authRemoteDataSourceProvider),
    tokenStorage: ref.read(secureTokenStorageProvider),
    pinStorage: ref.read(pinStorageProvider),
  );
}
