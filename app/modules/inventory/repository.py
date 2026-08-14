"""Accès aux données du module inventory."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor
from app.modules.inventory.models import StockMovement


class _CursorData(TypedDict):
    id: UUID
    created_at: datetime


def _parse_cursor(cursor: str) -> _CursorData | None:
    """Décode et valide un cursor opaque. Retourne None si invalide."""
    raw = decode_cursor(cursor)
    if raw is None:
        return None
    try:
        return _CursorData(
            id=UUID(str(raw["id"])),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )
    except (KeyError, ValueError):
        return None


class InventoryRepository:
    """Repository pour l'entité StockMovement."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, movement: StockMovement) -> StockMovement:
        """Crée et persiste un mouvement de stock."""
        self.db.add(movement)
        await self.db.flush()
        await self.db.refresh(movement)
        return movement

    async def list_movements(
        self,
        store_id: UUID,
        product_id: UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[StockMovement], bool]:
        """Liste les mouvements de stock avec pagination cursor-based.

        Tri par (created_at DESC, id DESC). Retourne (items, has_more).
        """
        stmt = select(StockMovement).where(StockMovement.store_id == store_id)

        if product_id is not None:
            stmt = stmt.where(StockMovement.product_id == product_id)

        if cursor:
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                stmt = stmt.where(
                    tuple_(StockMovement.created_at, StockMovement.id)
                    < (parsed["created_at"], parsed["id"])
                )

        stmt = stmt.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(
            limit + 1
        )

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more
