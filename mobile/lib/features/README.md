# Features

Chaque feature suit la même structure en 3 couches :

```
feature_name/
├── data/                     Couche données (concrète)
│   ├── datasources/
│   │   ├── feature_local_datasource.dart    Lit/écrit dans SQLite via drift
│   │   └── feature_remote_datasource.dart   Appelle l'API via dio/retrofit
│   ├── models/               DTO (avec freezed + json_serializable)
│   └── repositories/
│       └── feature_repository_impl.dart     Implémentation du repository
├── domain/                   Couche métier (abstraite, indépendante)
│   ├── entities/             Modèles métier (immutables, freezed)
│   ├── repositories/         Interfaces des repositories
│   └── usecases/             Cas d'usage métier
└── presentation/             Couche UI (Flutter + Riverpod)
    ├── pages/                Écrans complets
    ├── widgets/              Widgets spécifiques à la feature
    └── providers/            Providers Riverpod
```

## Règles de dépendances

- `presentation` peut importer `domain` (entities, usecases) — JAMAIS `data`
- `data` peut importer `domain` (pour implémenter les interfaces)
- `domain` n'importe JAMAIS de `data` ni de `presentation`
- Une feature peut importer le `domain` d'une autre feature, jamais sa `data`

Cette règle force le découplage : on peut changer d'API ou de DB locale sans impacter la couche UI.

## Liste des features

| Feature | Description | Statut |
|---|---|---|
| `auth` | Inscription, login, PIN, refresh token | Squelette |
| `catalog` | CRUD produits, recherche, scan | À implémenter |
| `sales` | Panier, paiement, validation, historique | À implémenter |
| `printing` | Bluetooth, impression ESC/POS | À implémenter |
| `sync` | Queue offline, synchronisation backend | À implémenter |
