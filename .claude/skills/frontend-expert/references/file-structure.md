# Structure de fichiers — POS Mobile

## Arborescence globale

```
lib/
├── core/
│   ├── database/        # drift : app_database.dart, tables/
│   ├── network/         # dio client, interceptors (auth, retry)
│   ├── sync/            # SyncQueue, SyncService, SyncWorker
│   ├── theme/           # AppTheme, AppColors, AppTextStyles
│   └── widgets/         # AmountDisplay, EmptyState, LoadingOverlay
│
├── features/
│   └── [feature]/
│       ├── domain/
│       │   ├── entities/        # [Feature].dart (freezed)
│       │   ├── repositories/    # i_[feature]_repository.dart (interface)
│       │   └── usecases/        # [Action][Feature]UseCase.dart (si justifié)
│       │
│       ├── data/
│       │   ├── datasources/     # [feature]_local_datasource.dart (drift)
│       │   │                    # [feature]_remote_datasource.dart (retrofit)
│       │   ├── models/          # [Feature]Dto.dart (freezed+json)
│       │   │                    # [feature]_dto.mapper.dart (extension)
│       │   └── repositories/    # [feature]_repository_impl.dart
│       │
│       ├── presentation/
│       │   ├── screens/         # [feature]_screen.dart
│       │   ├── widgets/         # widgets spécifiques à la feature
│       │   └── notifiers/       # [feature]_notifier.dart (AsyncNotifier)
│       │
│       └── providers/
│           └── [feature]_providers.dart
│
└── main.dart
```

## Convention de nommage par fichier

| Fichier | Convention | Exemple |
|---------|-----------|---------|
| Entité | `snake_case.dart` | `sale.dart` |
| Interface repo | `i_[noun]_repository.dart` | `i_sale_repository.dart` |
| DTO | `[noun]_dto.dart` | `sale_dto.dart` |
| Mapper | `[noun]_dto.mapper.dart` | `sale_dto.mapper.dart` |
| Impl repo | `[noun]_repository_impl.dart` | `sale_repository_impl.dart` |
| Datasource locale | `[noun]_local_datasource.dart` | `sale_local_datasource.dart` |
| Datasource remote | `[noun]_remote_datasource.dart` | `sale_remote_datasource.dart` |
| Notifier | `[noun]_notifier.dart` | `sale_notifier.dart` |
| Screen | `[noun]_screen.dart` | `sale_screen.dart` |
| Providers | `[noun]_providers.dart` | `sale_providers.dart` |

## Exemple complet : feature `sale`

```
lib/features/sale/
├── domain/
│   ├── entities/sale.dart
│   ├── entities/sale_item.dart
│   ├── repositories/i_sale_repository.dart
│   └── usecases/create_sale_usecase.dart   ← seulement si logique complexe
│
├── data/
│   ├── datasources/sale_local_datasource.dart
│   ├── datasources/sale_remote_datasource.dart
│   ├── models/sale_dto.dart
│   ├── models/sale_dto.mapper.dart
│   └── repositories/sale_repository_impl.dart
│
├── presentation/
│   ├── screens/sale_screen.dart
│   ├── screens/sale_detail_screen.dart
│   ├── widgets/sale_item_tile.dart
│   ├── widgets/sale_total_bar.dart
│   └── notifiers/sale_notifier.dart
│
└── providers/
    └── sale_providers.dart
```