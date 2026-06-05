# Flutter Flavors

Deux flavors : **dev** et **prod**. Même codebase, deux APK distincts avec ID, nom et API différents.

## Flavors

| Flavor | App name | Application ID | API |
|--------|----------|----------------|-----|
| `dev` | POS Dev | `com.example.mobile.dev` | `https://pos-mobile-vkuh.onrender.com` |
| `prod` | POS | `com.example.mobile` | `https://api.pos-mobile-ci.com` |

Les deux flavors peuvent coexister sur le même appareil (IDs distincts).

## Commandes

```bash
make run           # dev sur émulateur/device
make run-prod      # prod release

make build-apk-dev # APK debug dev
make build-apk     # APK release prod
```

Commandes Flutter équivalentes :

```bash
# Dev
flutter run --flavor dev -t lib/main.dart

# Prod
flutter run --release --flavor prod -t lib/main_prod.dart
flutter build apk --release --flavor prod -t lib/main_prod.dart
```

## Architecture

### Entry points

```
lib/
├── main.dart       ← dev (flavor dev, API staging) — point d'entrée par défaut IDE
└── main_prod.dart  ← prod (flavor prod, API prod)
```

Chaque entry point appelle `AppConfig.setup(...)` **avant** `runApp` :

```dart
// main.dart (dev)
AppConfig.setup(
  flavor: AppFlavor.dev,
  apiUrl: 'https://pos-mobile-vkuh.onrender.com',
);

// main_prod.dart (prod)
AppConfig.setup(
  flavor: AppFlavor.prod,
  apiUrl: 'https://api.pos-mobile-ci.com',
);
```

### AppConfig

`lib/core/config.dart` — lecture en runtime via `AppConfig.apiUrl`, `AppConfig.flavor`, `AppConfig.isDev`.

```dart
// Vérifier l'environnement dans le code
if (AppConfig.isDev) {
  // logs verbeux, feature flags dev, etc.
}

// Lire l'URL (utilisé dans dio_client.dart)
final url = AppConfig.apiUrl;
```

### Android (`android/app/build.gradle.kts`)

```kotlin
flavorDimensions += "env"

productFlavors {
    create("dev") {
        dimension = "env"
        applicationIdSuffix = ".dev"
        versionNameSuffix = "-dev"
        resValue("string", "app_name", "POS Dev")
    }
    create("prod") {
        dimension = "env"
        resValue("string", "app_name", "POS")
    }
}
```

`AndroidManifest.xml` utilise `@string/app_name` — la valeur est injectée par le flavor au build.

### iOS

Les flavors iOS (Schemes Xcode) ne sont pas encore configurés — l'app cible Android uniquement au MVP.

Pour configurer iOS plus tard :
1. Xcode → Product → Scheme → Manage Schemes → Dupliquer "Runner" × 2 (`dev`, `prod`)
2. Chaque Scheme → Build Configuration : `Debug-dev` / `Release-prod`
3. Runner → Info.plist → `CFBundleDisplayName` → `$(APP_NAME)` (variable Xcode)
4. Build Settings → User-Defined : `APP_NAME = POS Dev` pour dev, `APP_NAME = POS` pour prod

## Ajouter un troisième flavor (ex: staging)

1. `build.gradle.kts` — ajouter `create("staging") { ... }`
2. `lib/core/config.dart` — ajouter `staging` à l'enum `AppFlavor`
3. `lib/main_staging.dart` — créer avec `AppConfig.setup(flavor: AppFlavor.staging, apiUrl: '...')`
4. `Makefile` — ajouter `run-staging` et `build-apk-staging`

## FAQ

**Pourquoi pas `--dart-define` ?**
`--dart-define` requiert de passer la variable à chaque commande. Avec les flavors, la config est dans le code source versionné — pas de risque d'oublier le flag.

**`main.dart` = dev, est-ce normal ?**
Oui. L'IDE (VS Code, Android Studio) lance `main.dart` par défaut. On veut qu'un `flutter run` sans target lance dev, jamais prod.

**Comment savoir quel flavor tourne ?**
```dart
AppConfig.flavor  // AppFlavor.dev ou AppFlavor.prod
AppConfig.isDev   // bool
```
