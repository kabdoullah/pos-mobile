"""Accès aux données du module stores."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.images import ProcessedImage
from app.modules.stores.models import Store, StoreLogo


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

    async def get_logo(self, store_id: UUID) -> StoreLogo | None:
        """Logo de la boutique, ou None."""
        return await self.db.get(StoreLogo, store_id)

    async def upsert_logo(self, store: Store, image: ProcessedImage) -> Store:
        """Remplace le logo et met à jour sa version."""
        row = await self.get_logo(store.id)
        if row is None:
            row = StoreLogo(store_id=store.id)
            self.db.add(row)
        row.content = image.content
        row.content_type = image.content_type
        row.width = image.width
        row.height = image.height
        row.sha256 = image.sha256
        store.logo_version = image.sha256
        await self.db.flush()
        await self.db.refresh(store)
        return store

    async def delete_logo(self, store: Store) -> Store:
        """Supprime le logo (sans erreur s'il n'y en a pas)."""
        row = await self.get_logo(store.id)
        if row is not None:
            await self.db.delete(row)
        store.logo_version = None
        await self.db.flush()
        await self.db.refresh(store)
        return store
