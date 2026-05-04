.DEFAULT_GOAL := help

.PHONY: help install gen gen-watch run analyze format test clean

help: ## Liste les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances Flutter
	flutter pub get

gen: ## Génère le code (drift, freezed, riverpod, retrofit)
	dart run build_runner build --delete-conflicting-outputs

gen-watch: ## Lance la génération de code en mode watch
	dart run build_runner watch --delete-conflicting-outputs

run: ## Lance l'app sur l'appareil ou émulateur connecté
	flutter run --dart-define=API_URL=http://10.0.2.2:8000

run-prod: ## Lance avec l'URL de production
	flutter run --release --dart-define=API_URL=https://api.pos-mobile-ci.com

analyze: ## Vérifie le code statiquement
	flutter analyze

format: ## Formate le code Dart
	dart format lib test --set-exit-if-changed

test: ## Lance les tests
	flutter test

build-apk: ## Build l'APK release
	flutter build apk --release --dart-define=API_URL=https://api.pos-mobile-ci.com

clean: ## Nettoie les caches Flutter
	flutter clean
	rm -rf .dart_tool build
