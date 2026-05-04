.DEFAULT_GOAL := help

.PHONY: help install dev format lint type-check test test-cov migrate makemigration shell clean

help: ## Liste les commandes disponibles
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances (dev incluses) avec uv
	uv sync

dev: ## Démarre le serveur en mode dev avec auto-reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

format: ## Formate le code avec ruff
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Vérifie le code avec ruff (sans modifier)
	uv run ruff check .
	uv run ruff format --check .

type-check: ## Vérifie les types avec mypy
	uv run mypy app

test: ## Lance les tests
	uv run pytest

test-cov: ## Lance les tests avec rapport de couverture HTML
	uv run pytest --cov=app --cov-report=html
	@echo "Rapport disponible dans htmlcov/index.html"

migrate: ## Applique les migrations Alembic
	uv run alembic upgrade head

makemigration: ## Génère une nouvelle migration. Usage : make makemigration MSG="description"
	uv run alembic revision --autogenerate -m "$(MSG)"

migration-history: ## Affiche l'historique des migrations
	uv run alembic history --verbose

shell: ## Lance un shell Python avec le contexte de l'app
	uv run python -i -c "from app.core.db import *; from app.core.config import settings"

clean: ## Supprime les fichiers temporaires
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf htmlcov .coverage

seed: ## Crée des données de test (utilisateur, boutique, produits)
	uv run python scripts/seed_test_data.py
