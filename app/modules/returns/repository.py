"""Accès aux données du module returns."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.returns.models import SaleReturn, SaleReturnItem


class SaleReturnRepository:
    """Repository pour l'agrégat SaleReturn + SaleReturnItem."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, return_id: UUID) -> SaleReturn | None:
        stmt = (
            select(SaleReturn)
            .options(selectinload(SaleReturn.items))
            .where(SaleReturn.id == return_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def returned_quantities(self, sale_id: UUID) -> dict[UUID, int]:
        """Quantité déjà retournée par ligne de vente (sale_item_id → quantité)."""
        stmt = (
            select(SaleReturnItem.sale_item_id, func.sum(SaleReturnItem.quantity))
            .join(SaleReturn, SaleReturnItem.sale_return_id == SaleReturn.id)
            .where(SaleReturn.sale_id == sale_id)
            .group_by(SaleReturnItem.sale_item_id)
        )
        result = await self.db.execute(stmt)
        return {item_id: int(quantity) for item_id, quantity in result.all()}

    async def create(self, sale_return: SaleReturn) -> SaleReturn:
        """Insère le retour et ses lignes ; relit le numéro posé par le trigger."""
        self.db.add(sale_return)
        await self.db.flush()
        await self.db.refresh(sale_return, ["return_number", "synced_at"])
        return sale_return

    async def list_changed(
        self,
        store_id: UUID,
        since: datetime | None,
        limit: int,
        cursor_after_id: UUID | None = None,
        cursor_after_synced_at: datetime | None = None,
    ) -> tuple[list[SaleReturn], bool]:
        """Retours syncés depuis `since` (horloge serveur), avec leurs lignes."""
        stmt = (
            select(SaleReturn)
            .options(selectinload(SaleReturn.items))
            .where(SaleReturn.store_id == store_id)
        )
        if since is not None:
            stmt = stmt.where(SaleReturn.synced_at > since)
        if cursor_after_id is not None and cursor_after_synced_at is not None:
            stmt = stmt.where(
                tuple_(SaleReturn.synced_at, SaleReturn.id)
                > (cursor_after_synced_at, cursor_after_id)
            )
        stmt = stmt.order_by(SaleReturn.synced_at.asc(), SaleReturn.id.asc()).limit(limit + 1)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return rows, has_more
