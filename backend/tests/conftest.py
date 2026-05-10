"""Configuration pytest globale."""

import os
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from fastapi import Request

from app.core.config import settings
from app.core.db import get_db, get_tenant_db
from app.main import app

_TEST_DB_URL = settings.database_url.rsplit("/", 1)[0] + "/pos_test"
_BACKEND_DIR = Path(__file__).parent.parent

# Tables dans l'ordre pour TRUNCATE (enfants avant parents)
_ALL_TABLES = (
    "sale_items",
    "sales",
    "products",
    "email_verification_tokens",
    "password_reset_tokens",
    "stores",
    "users",
)


@pytest.fixture(scope="session", autouse=True)
def _migrate_test_db() -> None:
    """Recrée pos_test de zéro et applique les migrations Alembic.

    Utilise DROP + CREATE DATABASE pour garantir un état propre incluant les
    politiques RLS, triggers et types définis dans les migrations (absents de
    create_all). Requis pour les tests d'isolation RLS.
    """
    pg_container = "pos-mobile-postgres-1"
    pg_user = "pos"
    for sql in (
        "DROP DATABASE IF EXISTS pos_test WITH (FORCE)",
        "CREATE DATABASE pos_test WITH OWNER pos",
    ):
        subprocess.run(
            ["docker", "exec", pg_container, "psql", "-U", pg_user, "-c", sql],
            check=True,
            capture_output=True,
        )
    env = {**os.environ, "DATABASE_URL": _TEST_DB_URL}
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        env=env,
        cwd=str(_BACKEND_DIR),
        check=True,
    )
    # pos is a superuser → bypasses RLS entirely. Create pos_app (non-superuser) so
    # tests can SET LOCAL ROLE pos_app to actually enforce RLS policies.
    subprocess.run(
        [
            "docker",
            "exec",
            pg_container,
            "psql",
            "-U",
            pg_user,
            "-c",
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'pos_app') "
            "THEN CREATE ROLE pos_app NOLOGIN; END IF; END $$",
        ],
        check=True,
        capture_output=True,
    )
    for sql in (
        "GRANT CONNECT ON DATABASE pos_test TO pos_app",
        "GRANT USAGE ON SCHEMA public TO pos_app",
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pos_app",
    ):
        subprocess.run(
            ["docker", "exec", pg_container, "psql", "-U", pg_user, "-d", "pos_test", "-c", sql],
            check=True,
            capture_output=True,
        )


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Force le backend asyncio pour les tests."""
    return "asyncio"


@pytest.fixture
async def db_engine(_migrate_test_db: None):
    """Engine sur pos_test. TRUNCATE toutes les tables entre les tests.

    TRUNCATE bypass les politiques RLS et les triggers d'immuabilité,
    ce qui est voulu pour le nettoyage inter-tests.
    """
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {', '.join(_ALL_TABLES)} CASCADE"))
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Session de test avec rollback automatique."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Client HTTP async pour tester les endpoints FastAPI.

    Override get_tenant_db pour activer RLS (SET LOCAL ROLE pos_app) :
    le user pos est superuser et bypass RLS, pos_app ne l'est pas.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def override_get_tenant_db(request: Request) -> AsyncSession:
        store_id = getattr(request.state, "store_id", None)
        if store_id is not None:
            await db_session.execute(text("SET LOCAL ROLE pos_app"))
            await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))
        return db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
