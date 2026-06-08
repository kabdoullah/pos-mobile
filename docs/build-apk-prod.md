# Guide de build de production — POS Mobile (Ma Caisse)

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Étapes pré-build](#2-étapes-pré-build)
3. [Configuration de la signature release](#3-configuration-de-la-signature-release)
4. [Commandes de build](#4-commandes-de-build)
5. [Localisation des artefacts générés](#5-localisation-des-artefacts-générés)
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

### État actuel

`mobile/android/app/build.gradle.kts` charge `android/key.properties` et signe avec la clé de release si le fichier existe, avec fallback sur la clé debug sinon (pour les CI sans secrets) :

```kotlin
val keyPropertiesFile = rootProject.file("key.properties")
val keyProperties = Properties()
if (keyPropertiesFile.exists()) {
    keyProperties.load(keyPropertiesFile.inputStream())
}

signingConfigs {
    create("release") {
        keyAlias = keyProperties["keyAlias"] as String?
        keyPassword = keyProperties["keyPassword"] as String?
        storeFile = keyProperties["storeFile"]?.let { file(it as String) }
        storePassword = keyProperties["storePassword"] as String?
    }
}

buildTypes {
    release {
        signingConfig = if (keyPropertiesFile.exists()) {
            signingConfigs.getByName("release")
        } else {
            signingConfigs.getByName("debug")
        }
    }
}
```

### Fichiers de signature (hors git)

Ces deux fichiers sont exclus par `.gitignore` (`key.properties` et `**/*.jks`). Les créer localement ou les récupérer depuis le stockage sécurisé de l'équipe.

**`mobile/android/app/macaisse-release.jks`** — généré une seule fois :

```bash
keytool -genkey -v \
  -keystore mobile/android/app/macaisse-release.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias macaisse-key
```

**`mobile/android/key.properties`** :

```properties
storePassword=<mot_de_passe_keystore>
keyPassword=<mot_de_passe_clé>
keyAlias=macaisse-key
storeFile=../app/macaisse-release.jks
```

> **Important :** `storeFile` est relatif au répertoire `android/` (pas à la racine du projet).

---

## 4. Commandes de build

Toutes les commandes se lancent depuis `mobile/`.

### App Bundle AAB — Play Store (recommandé)

```bash
make build-aab
# = flutter build appbundle --release --flavor prod -t lib/main_prod.dart
```

Format requis pour la soumission sur le Google Play Store. Smaller download size grâce au delivery dynamique par architecture.

### APK prod (distribution directe / sideload)

```bash
make build-apk
# = flutter build apk --release --flavor prod -t lib/main_prod.dart
```

### APK par architecture (sideload optimisé)

Pour réduire la taille de l'APK distribué directement :

```bash
flutter build apk --release --flavor prod -t lib/main_prod.dart --split-per-abi
```

Génère trois APKs :
- `app-armeabi-v7a-prod-release.apk` — appareils 32 bits (entrée de gamme, courant en Côte d'Ivoire)
- `app-arm64-v8a-prod-release.apk` — appareils 64 bits modernes
- `app-x86_64-prod-release.apk` — émulateurs

Pour la distribution sideload, privilégier `arm64-v8a` sur les appareils récents et `armeabi-v7a` sur les anciens.

### APK dev (pour comparaison)

```bash
make build-apk-dev
# = flutter build apk --flavor dev -t lib/main.dart
```

Flavor "dev" : `applicationId = "ci.pos.macaisse.dev"`, `app_name = "Ma Caisse Dev"`, API sur `http://10.0.2.2:8000`. Les deux APKs peuvent coexister sur le même appareil.

---

## 5. Localisation des artefacts générés

### App Bundle (AAB)

```
mobile/build/app/outputs/bundle/prodRelease/app-prod-release.aab
```

### APK (universel)

```
mobile/build/app/outputs/flutter-apk/app-prod-release.apk
```

### APKs par ABI

```
mobile/build/app/outputs/flutter-apk/app-armeabi-v7a-prod-release.apk
mobile/build/app/outputs/flutter-apk/app-arm64-v8a-prod-release.apk
mobile/build/app/outputs/flutter-apk/app-x86_64-prod-release.apk
```

Vérification :

```bash
ls -lh mobile/build/app/outputs/bundle/prodRelease/
ls -lh mobile/build/app/outputs/flutter-apk/
```

---

## 6. Vérifications post-build

### 6.1 Inspecter les métadonnées de l'APK

```bash
$ANDROID_HOME/build-tools/<version>/aapt dump badging \
  mobile/build/app/outputs/flutter-apk/app-prod-release.apk \
  | grep -E "package|version|application-label"
```

Valeurs attendues :
- `package='ci.pos.macaisse'` (pas `.dev`)
- `versionCode='1'` et `versionName='1.0.0'`
- `application-label:'Ma Caisse'`

### 6.2 Vérifier la signature

APK :
```bash
keytool -printcert -jarfile \
  mobile/build/app/outputs/flutter-apk/app-prod-release.apk
```

AAB :
```bash
keytool -printcert -jarfile \
  mobile/build/app/outputs/bundle/prodRelease/app-prod-release.aab
```

### 6.3 Installer et smoke test

```bash
adb uninstall ci.pos.macaisse
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

Vérifier le chemin dans `android/key.properties` :
- `storeFile` est **relatif à `android/`** : utiliser `../app/macaisse-release.jks`
- Le fichier `.jks` ne doit pas être dans le repo git

### `MissingPluginException` au lancement de l'APK release

```bash
make clean && make install && make build-apk
```

### L'APK prod pointe vers l'API de dev (`10.0.2.2`)

Cause : mauvais point d'entrée utilisé. Toujours utiliser `make build-apk` ou `make build-aab` qui passent `-t lib/main_prod.dart`. Ne jamais utiliser `flutter build apk --release` sans `--flavor` et `-t`.

---

## 8. Checklist résumée

```
[ ] make install            — dépendances à jour
[ ] make gen                — code généré à jour
[ ] make format             — aucun diff de formatage
[ ] make analyze            — 0 erreur
[ ] key.properties présent  — keystore de release configuré
[ ] make build-aab          — AAB Play Store (ou make build-apk pour sideload)
[ ] aapt dump badging       — applicationId = ci.pos.macaisse (pas .dev)
[ ] keytool -printcert      — signature release vérifiée (pas debug)
[ ] adb install + smoke     — login, PIN, réseau prod OK
```
