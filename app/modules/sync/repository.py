"""Accès aux données du module sync."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product
from app.modules.sales.models import Sale


class SyncRepository:
    """Repository pour les opérations de synchronisation cross-table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_changed_products(
        self,
        store_id: UUID,
        since: datetime | None,
        limit: int,
        cursor_after_id: UUID | None = None,
        cursor_after_updated_at: datetime | None = None,
    ) -> tuple[list[Product], bool]:
        """Produits modifiés ou soft-deleted depuis `since`.

        Inclut les produits supprimés (pas de filtre deleted_at IS NULL).
        Tri ASC pour que le client puisse rejouer les changements dans l'ordre.
        """
        stmt = select(Product).where(Product.store_id == store_id)

        if since is not None:
            stmt = stmt.where(
                or_(
                    Product.updated_at > since,
                    and_(Product.deleted_at.is_not(None), Product.deleted_at > since),
                )
            )

        if cursor_after_id is not None and cursor_after_updated_at is not None:
            stmt = stmt.where(
                tuple_(Product.updated_at, Product.id) > (cursor_after_updated_at, cursor_after_id)
            )

        stmt = stmt.order_by(Product.updated_at.asc(), Product.id.asc()).limit(limit + 1)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more

    async def list_changed_sales(
        self,
        store_id: UUID,
        since: datetime | None,
        limit: int,
        cursor_after_id: UUID | None = None,
        cursor_after_synced_at: datetime | None = None,
    ) -> tuple[list[Sale], bool]:
        """Ventes syncées depuis `since`, avec leurs items (selectinload).

        Utilise synced_at (horloge serveur) et non created_at (horloge client)
        pour garantir que le client ne rate aucune vente malgré le drift d'horloge.
        """
        stmt = select(Sale).options(selectinload(Sale.items)).where(Sale.store_id == store_id)

        if since is not None:
            stmt = stmt.where(Sale.synced_at > since)

        if cursor_after_id is not None and cursor_after_synced_at is not None:
            stmt = stmt.where(
                tuple_(Sale.synced_at, Sale.id) > (cursor_after_synced_at, cursor_after_id)
            )

        stmt = stmt.order_by(Sale.synced_at.asc(), Sale.id.asc()).limit(limit + 1)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more
