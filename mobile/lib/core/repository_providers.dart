import 'package:riverpod_annotation/riverpod_annotation.dart';

import '../features/catalog/data/repositories/catalog_repository_impl.dart';
import '../features/catalog/domain/repositories/catalog_repository.dart';
import '../features/sync/presentation/providers/sync_providers.dart';

part 'repository_providers.g.dart';

/// Provides the catalog repository implementation (local-first via drift).
@riverpod
CatalogRepository catalogRepository(Ref ref) {
  return CatalogRepositoryImpl(
    db: ref.watch(databaseProvider),
    syncQueue: ref.watch(syncQueueRepositoryProvider),
  );
}
