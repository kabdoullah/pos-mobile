import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../features/sync/presentation/providers/sync_providers.dart';
import '../data/repositories/sales_repository_impl.dart';
import '../domain/repositories/sales_repository.dart';
import '../domain/usecases/create_sale_usecase.dart';

part 'sales_di_providers.g.dart';

/// Provides the sales repository implementation (local-first via drift).
@riverpod
SalesRepository salesRepository(Ref ref) {
  return SalesRepositoryImpl(
    db: ref.watch(databaseProvider),
    syncQueue: ref.watch(syncQueueRepositoryProvider),
  );
}

/// Provides the create sale use case (business logic).
@riverpod
CreateSaleUseCase createSaleUseCase(Ref ref) {
  return CreateSaleUseCase(repository: ref.watch(salesRepositoryProvider));
}
