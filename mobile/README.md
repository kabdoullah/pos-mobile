# Mobile POS Mobile

Application Flutter pour les commerçants en Côte d'Ivoire.

## Stack

- **Flutter 3.22+** / Dart 3.4+
- **Riverpod 3** pour le state management
- **drift** pour SQLite local typé
- **dio + retrofit** pour l'API
- **mobile_scanner** pour les codes-barres
- **print_bluetooth_thermal + esc_pos_utils_plus** pour l'impression Bluetooth (ESC/POS 58mm)

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

## Build release Android (AAB)

```bash
make build-aab   # flutter build appbundle --release --flavor prod -t lib/main_prod.dart
```

### ABI cibles

`android/app/build.gradle.kts` limite le build à `arm64-v8a` et `armeabi-v7a` :

```kotlin
ndk {
    abiFilters += listOf("arm64-v8a", "armeabi-v7a")
}
```

`x86_64` est exclu — cette architecture ne correspond à aucun appareil Android vendu sur le marché ivoirien (uniquement émulateurs Intel). Le Play Store découpe l'AAB par ABI : l'utilisateur ne télécharge que les libs correspondant à son appareil.

### MLKit barcode — mode unbundled

`android/gradle.properties` contient :

```properties
dev.steenbakker.mobile_scanner.useUnbundled=true
```

Les modèles TFLite de `mobile_scanner` sont délégués à Google Play Services plutôt que bundlés dans l'AAB (-0.7 MB). Tous les appareils Android courants en CI ont Play Services à jour.

### Assets launcher icons

Les sources d'icônes (`icon_android_fg_dark.png`, `icon_android_legacy.png`, `icon_ios.png`, etc.) sont dans `assets/launcher_icons/` — hors du glob `assets/images/` déclaré dans `pubspec.yaml`. Ces fichiers ne sont utiles qu'au build-time via `flutter_launcher_icons` et ne doivent pas être embarqués dans le bundle Flutter.

Après toute modification d'icône, régénérer :

```bash
flutter pub run flutter_launcher_icons
```

### Prérequis build release

- **Android SDK cmdline-tools** doit être installé (`flutter doctor` doit passer sans `✗` sur Android toolchain). Installer via Android Studio → Settings → Android SDK → SDK Tools → "Android SDK Command-line Tools".
- **Keystore** configuré dans `android/key.properties` (voir `android/key.properties.example`).
