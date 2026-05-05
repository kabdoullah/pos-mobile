"""Logique métier du module stores."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.stores import schemas
from app.modules.stores.models import Store
from app.modules.stores.repository import StoreRepository

_DEFAULT_STORE_NAME = "Ma boutique"


class StoreService:
    """Service métier de la gestion des boutiques."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = StoreRepository(db)

    async def create_for_user(self, user_id: UUID, payload: schemas.StoreCreate) -> Store:
        """Crée une boutique pour l'utilisateur. Erreur si une boutique existe déjà."""
        existing = await self.repo.get_by_owner_id(user_id)
        if existing is not None:
            raise ConflictError("A store already exists for this user.", field="owner_id")

        store = Store(
            owner_id=user_id,
            name=payload.name,
            address=payload.address,
            ncc=payload.ncc,
            vat_subject=payload.vat_subject,
            receipt_footer_text=payload.receipt_footer_text,
        )
        return await self.repo.create(store)

    async def create_default_for_user(self, user_id: UUID) -> Store:
        """Crée une boutique vide avec les valeurs par défaut. Appelé à l'inscription."""
        store = Store(owner_id=user_id, name=_DEFAULT_STORE_NAME)
        return await self.repo.create(store)

    async def get_for_user(self, user_id: UUID) -> Store:
        """Retourne la boutique de l'utilisateur ou lève NotFoundError."""
        store = await self.repo.get_by_owner_id(user_id)
        if store is None:
            raise NotFoundError("Store not found.")
        return store

    async def update_for_user(self, user_id: UUID, payload: schemas.StoreUpdate) -> Store:
        """Met à jour les champs fournis de la boutique (PATCH partiel)."""
        store = await self.get_for_user(user_id)
        updates = payload.model_dump(exclude_unset=True)
        return await self.repo.update(store, updates)
