---
description: Conventions et patterns spécifiques au mobile Flutter
globs:
  - "mobile/**/*.dart"
  - "mobile/pubspec.yaml"
  - "mobile/analysis_options.yaml"
---

# Conventions mobile (Flutter / Dart)

## Architecture feature-first + Clean Architecture allégée

Voir `mobile/lib/features/README.md` pour les détails. Règles de dépendances strictes :

- `presentation` → peut importer `domain`, JAMAIS `data`
- `data` → implémente les interfaces de `domain`
- `domain` → n'importe RIEN d'autre (entités pures, indépendantes)

Une feature peut importer le `domain` d'une autre feature, jamais sa `data`.

## Conventions Dart

- Single quotes pour les strings (`'hello'`, pas `"hello"`)
- Trailing commas obligatoires (formatage automatique cohérent)
- Pas de `dynamic` (le linter est en `strict-casts` et `strict-raw-types`)
- Pas de `print` : utiliser le package `logger`
- Toute API publique (classe, méthode, getter) doit être documentée (`public_member_api_docs`)

## State management : Riverpod

- Tous les états globaux passent par Riverpod
- Préférer les providers générés via `riverpod_generator` quand c'est possible
- Les providers d'une feature sont dans `<feature>/presentation/providers/`
- Pas de `StatefulWidget` avec state local quand un provider serait plus propre

## Persistance locale : drift

- Tables définies dans `mobile/lib/database/app_database.dart`
- Le code généré (`app_database.g.dart`) ne doit JAMAIS être édité à la main
- Après chaque modif des tables, lancer `make gen` (ou avoir `make gen-watch` qui tourne)
- Les montants en FCFA sont stockés en `TextColumn` (préservation précision décimale)

## Sync offline-online

Voir `docs/adr/0003-sync-hybride.md`. Règles :

- **Ventes** : événementiel append-only via `sync_queue`. UUID v4 généré côté client (idempotence).
- **Catalogue** : flag `dirty=true` sur les produits modifiés. Push état complet au backend.
- Pull au démarrage et au retour de connectivité via `GET /sync/changes?since=...`.

## Auth et stockage sécurisé

- JWT (access + refresh) stockés dans `flutter_secure_storage`
- PIN local hashé bcrypt avant stockage dans `flutter_secure_storage`
- Le PIN n'est JAMAIS envoyé au backend
- 5 tentatives max de PIN, puis blocage 5 min (voir `core/config.dart`)

## Génération de code (build_runner)

Packages qui génèrent du code : `drift_dev`, `freezed`, `json_serializable`, `riverpod_generator`, `retrofit_generator`.

Commande : `make gen` (ou `make gen-watch` pour le mode watch).

Les fichiers générés (`*.g.dart`, `*.freezed.dart`) sont exclus de l'analyzer dans `analysis_options.yaml`.

## Tests

- Tests dans `test/` à plat, pas dans une arbo qui mime `lib/`
- Convention de nommage : `<feature>_<chose>_test.dart` (ex: `auth_service_test.dart`)
- Mocker via `mocktail` (pas `mockito` qui demande de la génération de code)

## Performance

- `const` constructors partout où possible (économise le rebuild)
- `ListView.builder` pour les listes longues
- `StreamProvider` pour observer les changements drift en temps réel
