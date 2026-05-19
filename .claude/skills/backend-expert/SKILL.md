---
name: backend-expert
description: Expertise backend FastAPI du projet POS. Utiliser pour toute génération de code ou prompt backend (modules, endpoints, repository, migrations, RLS).
---

# Backend Expert — POS Mobile

## Stack
FastAPI, PostgreSQL, SQLAlchemy 2.0 (async), Alembic, uv, ruff. 100% open source.

## Architecture
Monolithe modulaire. Chaque module : router / service / repository / schemas / models.
- Communication inter-modules via les services, jamais repository/models cross-module (sauf repository réutilisable documenté).
- Multi-tenancy : colonne store_id NOT NULL + index + Row-Level Security PostgreSQL sur chaque table tenant. Test d'isolation RLS OBLIGATOIRE pour toute nouvelle table tenant.
- Ventes immuables (trigger PostgreSQL bloque UPDATE/DELETE). Idempotence par UUID client (INSERT ON CONFLICT DO NOTHING).
- receipt_number généré par trigger PostgreSQL atomique, jamais côté Python.

## Règles SQLAlchemy
- flush() dans les repositories, commit() centralisé dans get_db() (jamais de commit dans repo/service).
- expire_on_commit=False, autoflush=False obligatoires (async).
- Montants : NUMERIC(12,2) en base, transitent en String décimale dans l'API.

## Migrations
RLS, triggers, fonctions PL/pgSQL en SQL raw via op.execute(). Tester upgrade ET downgrade. Migration 0001 est la référence.

## Conventions
Endpoints au pluriel. Pagination cursor-based. Conventional Commits (scope: backend/auth/catalog/sales/sync/stores). Validation Pydantic v2 (field_validator/model_validator, pas v1).

## Format de prompt à produire
Quand on me demande d'implémenter un module backend, je découpe en prompts séquentiels (schémas → repository → service → router → tests), chacun avec : structure de fichiers imposée explicite, conventions rappelées, vérifications post-prompt (grep + make analyze + make test), un commit conventionnel. UN prompt à la fois, validation entre chaque.
