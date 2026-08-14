"""Accès aux données du module catalog."""

from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor
from app.modules.catalog.models import Product


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


class ProductRepository:
    """Repository pour l'entité Product."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_by_id(self, product_id: UUID, store_id: UUID) -> Product | None:
        """Retourne un produit actif par son id, ou None."""
        stmt = select(Product).where(
            Product.id == product_id,
            Product.store_id == store_id,
            Product.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_barcode(self, barcode: str, store_id: UUID) -> Product | None:
        """Retourne un produit actif par son code-barres, ou None."""
        stmt = select(Product).where(
            Product.barcode == barcode,
            Product.store_id == store_id,
            Product.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(
        self,
        store_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> tuple[list[Product], bool]:
        """Liste les produits actifs avec pagination cursor-based.

        Tri par (created_at DESC, id DESC). Retourne (items, has_more).
        """
        stmt = select(Product).where(Product.store_id == store_id, Product.deleted_at.is_(None))

        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))

        if low_stock_only:
            stmt = stmt.where(
                Product.current_stock.isnot(None),
                Product.min_stock.isnot(None),
                Product.current_stock <= Product.min_stock,
            )

        if cursor:
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                stmt = stmt.where(
                    tuple_(Product.created_at, Product.id) < (parsed["created_at"], parsed["id"])
                )

        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc()).limit(limit + 1)

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more

    async def create(self, product: Product) -> Product:
        """Crée et persiste un produit."""
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def update(self, product: Product, updates: dict[str, Any]) -> Product:
        """Applique les champs fournis et persiste."""
        for field, value in updates.items():
            setattr(product, field, value)
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def adjust_stock(self, product: Product, delta: int, enable_tracking: bool) -> int | None:
        """Applique un delta sur current_stock.

        Si enable_tracking=True, active le suivi si le produit n'était pas encore
        suivi (NULL -> COALESCE(0) + delta). Si enable_tracking=False (vente), ne
        touche jamais un produit non suivi : current_stock reste NULL (choix
        délibéré du commerçant de ne pas suivre ce produit).
        Pas de garde-fou de non-négativité : le stock peut aller sous zéro.

        Lost update possible sous écriture concurrente sur le même produit (pas de
        FOR UPDATE) : accepté, décision produit actée (le stock ne bloque jamais
        une vente, un léger désynchronisme n'est pas une violation d'invariant).
        """
        if product.current_stock is None:
            if not enable_tracking:
                return None
            product.current_stock = delta
        else:
            product.current_stock = product.current_stock + delta
        await self.db.flush()
        await self.db.refresh(product)
        return product.current_stock

    async def set_stock_null(self, product: Product) -> None:
        """Désactive le tracking du stock (current_stock -> NULL)."""
        product.current_stock = None
        await self.db.flush()
        await self.db.refresh(product)

    async def soft_delete(self, product: Product) -> None:
        """Marque le produit comme supprimé (soft delete)."""
        product.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def get_by_id_including_deleted(self, product_id: UUID) -> Product | None:
        """Retourne un produit par son id, deleted ou non."""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_barcode_excluding(
        self, barcode: str, exclude_id: UUID
    ) -> Product | None:
        """Retourne un produit actif avec ce barcode, en excluant un id donné."""
        stmt = select(Product).where(
            Product.barcode == barcode,
            Product.deleted_at.is_(None),
            Product.id != exclude_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
