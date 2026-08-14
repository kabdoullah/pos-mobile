"""Accès aux données du module stores."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.stores.models import Store


class StoreRepository:
    """Repository pour l'entité Store."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, store_id: UUID) -> Store | None:
        """Retourne la boutique par son id, ou None."""
        stmt = select(Store).where(Store.id == store_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_owner_id(self, owner_id: UUID) -> Store | None:
        """Retourne la boutique d'un utilisateur, ou None."""
        stmt = select(Store).where(Store.owner_id == owner_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, store: Store) -> Store:
        """Crée et persiste une boutique."""
        self.db.add(store)
        await self.db.flush()
        await self.db.refresh(store)
        return store

    async def update(self, store: Store, updates: dict[str, Any]) -> Store:
        """Applique les champs fournis et persiste."""
        for field, value in updates.items():
            setattr(store, field, value)
        await self.db.flush()
        await self.db.refresh(store)
        return store
