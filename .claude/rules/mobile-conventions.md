---
description: Conventions et patterns spécifiques au mobile Flutter
globs:
  - "mobile/**/*.dart"
  - "mobile/pubspec.yaml"
  - "mobile/analysis_options.yaml"
---

# Conventions mobile (Flutter / Dart)

## Architecture feature-first + Clean Architecture allégée

Voir `mobile/lib/features/README.md` pour les détails. **4 couches par feature :**

```
feature_name/
├── domain/       Entités, interfaces repository, usecases (Dart pur, ZÉRO Riverpod/Flutter)
├── data/         Implémentations concrètes (datasources, models, repository impl)
├── providers/    Couche DI : instancie les repos et usecases (exposé au domain)
└── presentation/ UI (pages, widgets, state notifiers consomment providers/)
```

**Règles strictes :**
- `domain` n'importe RIEN (Dart pur)
- `data` importe `domain` uniquement
- `providers/` importe `data` ET `domain` — c'est le SEUL endroit hors data autorisé à connaître data/
- `presentation` importe `domain` et `providers/` — JAMAIS `data` directement
- Une feature peut importer le `domain` (et `providers/`) d'une autre feature, jamais sa `data`

## Conventions Dart

- Single quotes pour les strings (`'hello'`, pas `"hello"`)
- Trailing commas obligatoires (formatage automatique cohérent)
- Pas de `dynamic` (le linter est en `strict-casts` et `strict-raw-types`)
- Pas de `print` : utiliser le package `logger`
- Toute API publique (classe, méthode, getter) doit être documentée (`public_member_api_docs`)

## State management : Riverpod

- Tous les états globaux passent par Riverpod 3+
- Préférer les providers générés via `riverpod_generator` quand c'est possible
- **Deux types de providers, deux emplacements :**
  - **DI providers** (repository, usecase, datasource) → `<feature>/providers/<feature>_di_providers.dart`
  - **UI state providers** (notifiers, asyncValue) → `<feature>/presentation/providers/`
- Pas de `StatefulWidget` avec state local quand un provider serait plus propre

## Persistance locale : drift

- Tables définies dans `mobile/lib/database/app_database.dart`
- Le code généré (`app_database.g.dart`) ne doit JAMAIS être édité à la main
- Après chaque modif des tables, lancer `make gen` (ou avoir `make gen-watch` qui tourne)
- Les montants en FCFA sont stockés en `TextColumn` (préservation précision décimale)

## Montants monétaires (FCFA)

**Règle fondamentale : le type `Decimal` (package `decimal: ^3.0.0`) est le seul type autorisé pour les montants dans la couche domain.**

| Couche | Type | Raison |
|--------|------|--------|
| API DTO (`core/network/api_models/`) | `String` | Sérialisation JSON exacte |
| Drift DB (`database/`) | `TextColumn` → `String` | Pas de type NUMERIC en SQLite, précision décimale |
| Domain entities | `Decimal` | Arithmétique exacte, pas de perte de précision |
| Presentation | `Decimal` (passé au widget) | Reçoit le type domain directement |

**Conversions :**
- API → domain : `Decimal.parse(stringValue)` — dans les mappers uniquement, throw si malformé (fail-fast à la frontière)
- domain → Drift : `decimalValue.toString()` — dans les mappers uniquement
- Drift → domain : `Decimal.parse(stringValue)` — dans les mappers uniquement
- Saisie utilisateur → validation : `Decimal.tryParse(text)` — retourne `null` si invalide (NE PAS utiliser `int.parse`)

**Interdit :**
- `int.parse(montant)` sur un champ monétaire — silencieusement faux sur les prix décimaux
- `double` pour les montants — perte de précision sur les grands entiers FCFA
- `num` comme type de paramètre pour les widgets monétaires

**Calculs :**
- Ligne de panier : `unitPrice * Decimal.fromInt(quantity)` (pas `Decimal.parse(quantity.toString())`)
- Total panier : `items.fold(Decimal.zero, (sum, item) => sum + item.lineTotal)`
- Rendu monnaie : `received - cartTotal` (les deux `Decimal`)

**Affichage (`AmountDisplay`) :**
- Accepte `Decimal amount`
- Formatte via `NumberFormat('#,##0', 'fr_FR').format(amount.toDouble())`
- `toDouble()` est sans perte pour les montants FCFA (entiers < 2^53)

## Sync offline-online

Voir `docs/adr/0003-sync-hybride.md`. Règles :

- **Ventes** : événementiel append-only via `sync_queue`. UUID v4 généré côté client (idempotence).
- **Catalogue** : flag `dirty=true` sur les produits modifiés. Push état complet au backend.
- Pull au démarrage et au retour de connectivité via `GET /sync/changes?since=...`.

## Auth et stockage sécurisé

- JWT (access + refresh) stockés dans `flutter_secure_storage`
- PIN local hashé PBKDF2-HMAC-SHA256 (sel aléatoire via `Random.secure`) avant stockage dans `flutter_secure_storage`
- Le PIN n'est JAMAIS envoyé au backend
- 5 tentatives max de PIN, puis blocage 5 min (voir `core/config.dart`)

## Impression Bluetooth

- Transport : package `print_bluetooth_thermal` (PAS flutter_blue_plus). Voir docs/adr/0007.
- Génération des commandes : `esc_pos_utils_plus`
- L'imprimante cible MVP est la Goojprt PT-210 (thermique 58mm ESC/POS, 32 caractères par ligne en monospace)
- Toujours gérer les 3 cas d'échec : imprimante non appairée, connexion perdue, échec d'envoi → proposer à l'utilisateur Réessayer / Plus tard / Pas de reçu


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
