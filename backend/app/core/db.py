"""Configuration SQLAlchemy async + injection du store_id pour le RLS."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID  # noqa: TC003

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,
    echo=settings.environment == "local",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI : fournit une session async, gère commit/rollback."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_tenant_db(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncSession:
    """Dépendance pour les routes authentifiées : injecte le store_id RLS.

    Le middleware StoreContextMiddleware a stocké le store_id dans request.state
    après validation du JWT. On l'injecte ici dans la session PostgreSQL pour
    activer le filtrage Row-Level Security.
    """
    store_id: UUID | None = getattr(request.state, "store_id", None)
    if store_id is not None:
        # SET LOCAL ne supporte pas les paramètres bindés en PostgreSQL — UUID est safe à inliner.
        await db.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))
    return db


# Type aliases pour réduire le boilerplate dans les routes
DbSession = Annotated[AsyncSession, Depends(get_db)]
TenantDbSession = Annotated[AsyncSession, Depends(get_tenant_db)]
