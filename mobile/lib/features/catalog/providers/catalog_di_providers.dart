import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../../../features/sync/presentation/providers/sync_providers.dart';
import '../data/repositories/catalog_repository_impl.dart';
import '../domain/repositories/catalog_repository.dart';

part 'catalog_di_providers.g.dart';

/// Provides the catalog repository implementation (local-first via drift).
@riverpod
CatalogRepository catalogRepository(Ref ref) {
  return CatalogRepositoryImpl(
    db: ref.watch(databaseProvider),
    syncQueue: ref.watch(syncQueueRepositoryProvider),
  );
}
