# Guide de build APK de production — POS Mobile (Ma Caisse)

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Étapes pré-build](#2-étapes-pré-build)
3. [Configuration de la signature release](#3-configuration-de-la-signature-release)
4. [Commande de build](#4-commande-de-build)
5. [Localisation de l'APK généré](#5-localisation-de-lapk-généré)
6. [Vérifications post-build](#6-vérifications-post-build)
7. [Erreurs communes et solutions](#7-erreurs-communes-et-solutions)
8. [Checklist résumée](#8-checklist-résumée)

---

## 1. Prérequis

### Outils requis

| Outil | Version minimale | Vérification |
|---|---|---|
| Flutter (channel stable) | 3.44.x | `flutter --version` |
| Dart | 3.12.x (inclus avec Flutter) | `dart --version` |
| Android SDK | Installé via Android Studio | `echo $ANDROID_HOME` |
| Java (JDK) | 17 | `java -version` |

Les chemins sont configurés dans `mobile/android/local.properties` :

```
sdk.dir=/home/<user>/Android/Sdk
flutter.sdk=/home/<user>/flutter
```

Ce fichier est ignoré par git. Sur une nouvelle machine, il est regénéré automatiquement par `flutter build` si `$ANDROID_HOME` est défini.

### Version de l'application

Définie dans `mobile/pubspec.yaml` :

```yaml
version: 1.0.0+1
         ^^^^^  ^ versionCode (Play Store)
         versionName (affiché à l'utilisateur)
```

Ces valeurs sont lues dynamiquement par Gradle via `flutter.versionName` et `flutter.versionCode`.

### Point d'entrée et URL d'API prod

`mobile/lib/main_prod.dart` configure :

- **Flavor** : `AppFlavor.prod`
- **API URL** : `https://pos-mobile-vkuh.onrender.com`
- **Token storage** : `flutter_secure_storage` (JWT)
- **Mode debug** : désactivé (`AppConfig.isDev` retourne `false`)

Aucune variable d'environnement à fournir au moment du build : l'URL est codée dans `main_prod.dart`.

---

## 2. Étapes pré-build

Depuis `mobile/`, exécuter dans l'ordre :

### Étape 1 — Installer les dépendances

```bash
make install
# = flutter pub get
```

À faire après tout `git pull` ou modification de `pubspec.yaml`.

### Étape 2 — Regénérer le code

```bash
make gen
# = dart run build_runner build --delete-conflicting-outputs
```

Obligatoire après toute modification de :
- `lib/database/app_database.dart` (schéma drift)
- Un fichier annoté `@freezed`, `@JsonSerializable`, `@riverpod`, ou `@RestApi`

### Étape 3 — Formater le code

```bash
make format
# = dart format lib test --set-exit-if-changed
```

Retourne un code de sortie non nul si des fichiers ont été reformatés. Committer les changements avant de continuer.

### Étape 4 — Analyse statique

```bash
make analyze
# = flutter analyze
```

Aucune erreur tolérée avant le build.

---

## 3. Configuration de la signature release

### Situation actuelle

`mobile/android/app/build.gradle.kts` contient :

```kotlin
buildTypes {
    release {
        // Signing with debug keys until a release keystore is configured.
        signingConfig = signingConfigs.getByName("debug")
    }
}
```

> **L'APK prod actuel est signé avec la clé de debug.** Fonctionnel pour la distribution directe (sideload) et les tests internes, mais interdit pour une publication sur le Google Play Store.

### Pour passer en signature de production (Play Store)

#### A. Générer un keystore de release

```bash
keytool -genkey -v \
  -keystore ~/keystores/pos-mobile-release.jks \
  -keyalg RSA \
  -keysize 2048 \
  -validity 10000 \
  -alias pos-mobile
```

Stocker ce fichier **hors du dépôt git**. Le `.gitignore` exclut déjà `**/*.keystore` et `**/*.jks`.

#### B. Créer `android/key.properties`

Ce fichier est exclu du git. Le créer localement :

```properties
storePassword=<mot_de_passe_keystore>
keyPassword=<mot_de_passe_clé>
keyAlias=pos-mobile
storeFile=/home/<user>/keystores/pos-mobile-release.jks
```

#### C. Modifier `android/app/build.gradle.kts`

```kotlin
import java.util.Properties
import java.io.FileInputStream

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(FileInputStream(keystorePropertiesFile))
}

android {
    signingConfigs {
        create("release") {
            keyAlias = keystoreProperties["keyAlias"] as String
            keyPassword = keystoreProperties["keyPassword"] as String
            storeFile = file(keystoreProperties["storeFile"] as String)
            storePassword = keystoreProperties["storePassword"] as String
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

---

## 4. Commande de build

### Build APK prod (release)

```bash
make build-apk
# = flutter build apk --release --flavor prod -t lib/main_prod.dart
```

Paramètres importants :
- `--release` : minification, obfuscation Dart, optimisations (supprime le banner debug, active R8)
- `--flavor prod` : `applicationId = "com.example.mobile"`, `app_name = "POS"`
- `-t lib/main_prod.dart` : point d'entrée avec `AppFlavor.prod` et l'URL API prod

### Build APK dev (pour comparaison)

```bash
make build-apk-dev
# = flutter build apk --flavor dev -t lib/main.dart
```

Flavor "dev" : `applicationId = "com.example.mobile.dev"`, `app_name = "POS Dev"`, API sur `http://10.0.2.2:8000`. Les deux APKs peuvent coexister sur le même appareil.

### Build par architecture (distribution sideload optimisée)

Pour réduire la taille de l'APK :

```bash
flutter build apk --release --flavor prod -t lib/main_prod.dart --split-per-abi
```

Génère trois APKs :
- `app-armeabi-v7a-prod-release.apk` — appareils 32 bits (entrée de gamme, courant en Côte d'Ivoire)
- `app-arm64-v8a-prod-release.apk` — appareils 64 bits modernes
- `app-x86_64-prod-release.apk` — émulateurs

Pour la distribution sideload, privilégier `arm64-v8a` sur les appareils récents et `armeabi-v7a` sur les anciens.

---

## 5. Localisation de l'APK généré

```
mobile/build/app/outputs/flutter-apk/app-prod-release.apk
```

Vérification :

```bash
ls -lh mobile/build/app/outputs/flutter-apk/
```

---

## 6. Vérifications post-build

### 6.1 Inspecter les métadonnées

```bash
$ANDROID_HOME/build-tools/<version>/aapt dump badging \
  mobile/build/app/outputs/flutter-apk/app-prod-release.apk \
  | grep -E "package|version|application-label"
```

Valeurs attendues :
- `package='com.example.mobile'` (pas `.dev`)
- `versionCode='1'` et `versionName='1.0.0'`
- `application-label:'POS'`

### 6.2 Vérifier la signature

```bash
keytool -printcert -jarfile \
  mobile/build/app/outputs/flutter-apk/app-prod-release.apk
```

### 6.3 Installer et smoke test

```bash
adb uninstall com.example.mobile
adb install mobile/build/app/outputs/flutter-apk/app-prod-release.apk
```

Points à vérifier :
- Bannière "DEBUG" absente
- Écran de connexion s'ouvre
- Réseau atteint `https://pos-mobile-vkuh.onrender.com` (premier appel ~50s — cold start Render free tier attendu, timeout configuré à 60s)
- Login + PIN fonctionnels

---

## 7. Erreurs communes et solutions

### `Gradle build failed: Kotlin version incompatible`

```bash
flutter clean && make install && make build-apk
```

Si persistant, vérifier la version Gradle dans `android/gradle/wrapper/gradle-wrapper.properties`.

### `build_runner: Conflict` lors de `make gen`

`--delete-conflicting-outputs` est déjà dans la commande. Si le problème persiste :

```bash
make clean && make install && make gen
```

### `Execution failed for task ':app:packageProdRelease'` — keystore introuvable

Vérifier le chemin absolu `storeFile=` dans `android/key.properties`. Le fichier `.jks` ne doit pas être dans le repo.

### `MissingPluginException` au lancement de l'APK release

```bash
make clean && make install && make build-apk
```

### L'APK prod pointe vers l'API de dev (`10.0.2.2`)

Cause : mauvais point d'entrée utilisé. Toujours utiliser `make build-apk` qui passe `-t lib/main_prod.dart`. Ne jamais utiliser `flutter build apk --release` sans `--flavor` et `-t`.

---

## 8. Checklist résumée

```
[ ] make install            — dépendances à jour
[ ] make gen                — code généré à jour
[ ] make format             — aucun diff de formatage
[ ] make analyze            — 0 erreur
[ ] make build-apk          — build réussi
[ ] aapt dump badging       — applicationId = com.example.mobile (pas .dev)
[ ] keytool -printcert      — signature vérifiée
[ ] adb install + smoke     — login, PIN, réseau prod OK
```
