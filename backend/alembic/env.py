"""Environnement Alembic configuré pour SQLAlchemy async."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.db import Base, _asyncpg_url_and_ssl

# Import explicite des modèles pour que Alembic les détecte
# Ajouter ici chaque nouveau module avec des modèles
from app.modules.auth import models as auth_models
from app.modules.catalog import models as catalog_models
from app.modules.sales import models as sales_models
from app.modules.stores import models as stores_models

config = context.config
_clean_url, _ssl_connect_args = _asyncpg_url_and_ssl(settings.database_url)
config.set_main_option("sqlalchemy.url", _clean_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Migrations en mode 'offline' (génère du SQL sans connexion)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Exécute les migrations sur une connexion synchrone."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Création de l'engine async puis exécution via run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_ssl_connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Lance les migrations en mode 'online' (avec connexion DB)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
