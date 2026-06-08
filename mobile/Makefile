.DEFAULT_GOAL := help

.PHONY: help install gen gen-watch run run-prod analyze format test build-apk build-apk-dev build-aab clean

help: ## Liste les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances Flutter
	flutter pub get

gen: ## Génère le code (drift, freezed, riverpod, retrofit)
	dart run build_runner build --delete-conflicting-outputs

gen-watch: ## Lance la génération de code en mode watch
	dart run build_runner watch --delete-conflicting-outputs

run: ## Lance l'app en mode dev (flavor dev, API staging)
	flutter run --flavor dev -t lib/main.dart

run-prod: ## Lance l'app en mode prod (flavor prod, API prod) — release
	flutter run --release --flavor prod -t lib/main_prod.dart

analyze: ## Vérifie le code statiquement
	flutter analyze

format: ## Formate le code Dart
	dart format lib test --set-exit-if-changed

test: ## Lance les tests
	flutter test

build-apk: ## Build l'APK release prod
	flutter build apk --release --flavor prod -t lib/main_prod.dart

build-apk-dev: ## Build l'APK dev (debug)
	flutter build apk --flavor dev -t lib/main.dart

build-aab: ## Build le AAB release prod (Play Store)
	flutter build appbundle --release --flavor prod -t lib/main_prod.dart

clean: ## Nettoie les caches Flutter
	flutter clean
	rm -rf .dart_tool build
