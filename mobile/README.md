# Mobile POS Mobile

Application Flutter pour les commerçants en Côte d'Ivoire.

## Stack

- **Flutter 3.22+** / Dart 3.4+
- **Riverpod 3** pour le state management
- **drift** pour SQLite local typé
- **dio + retrofit** pour l'API
- **mobile_scanner** pour les codes-barres
- **flutter_blue_plus + esc_pos_utils_plus** pour l'impression Bluetooth

## Démarrage rapide

```bash
# Installer les dépendances
make install

# Générer le code (drift, freezed, riverpod, retrofit)
make gen

# Lancer sur émulateur Android (le backend doit tourner sur le host)
make run

# Lancer en mode watch (régénère le code automatiquement)
make gen-watch
```

## Structure (feature-first + clean architecture)

```
mobile/
├── lib/
│   ├── main.dart
│   ├── core/                  Code transverse (theme, config, errors)
│   ├── features/              Une feature = une fonctionnalité métier
│   │   ├── auth/
│   │   │   ├── data/          DataSources, models DTO, repository impl
│   │   │   ├── domain/        Entities, repository interface, usecases
│   │   │   └── presentation/  Pages, widgets, providers Riverpod
│   │   ├── catalog/
│   │   ├── sales/
│   │   ├── printing/
│   │   └── sync/
│   ├── shared/                Widgets et helpers partagés
│   └── database/              Configuration drift
├── test/                      Tests Flutter
├── pubspec.yaml
├── analysis_options.yaml      Lints stricts
└── Makefile
```

Voir `lib/features/README.md` pour les règles de dépendances entre couches.

## Conventions

- **Pas de `print`**, utiliser le package `logger`
- **Pas de `dynamic`**, le `analysis_options.yaml` est strict
- **Single quotes** pour les strings
- **Trailing commas** obligatoires (formatage automatique cohérent)
- **public_member_api_docs** : toute API publique doit être documentée

## Commandes utiles

```bash
make help        # liste les commandes
make analyze     # vérifie statiquement
make format      # formate
make test        # lance les tests
make build-apk   # build release APK
```

## Configuration au build

L'URL de l'API est passée via `--dart-define` :

- Émulateur Android local : `http://10.0.2.2:8000`
- Production : `https://api.pos-mobile-ci.com`
