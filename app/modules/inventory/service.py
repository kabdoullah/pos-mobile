"""Logique métier du module inventory.

Dépendance à sens UNIQUE vers catalog (inventory -> catalog, jamais l'inverse)
pour éviter un import circulaire : inventory a besoin de muter products.current_stock,
donc catalog ne doit jamais importer inventory.
"""

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.core.pagination import CursorPage, encode_cursor
from app.modules.catalog.service import ProductService
from app.modules.inventory.models import StockMovement
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import StockMovementReason, StockMovementResponse

logger = structlog.get_logger()


class InventoryService:
    """Service métier de la traçabilité des mouvements de stock."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = InventoryRepository(db)
        self.product_service = ProductService(db)

    async def record_manual_adjustment(
        self,
        store_id: UUID,
        product_id: UUID,
        quantity_delta: int,
        note: str | None,
        user_id: UUID,
    ) -> StockMovement:
        """Ajustement manuel du stock (réception, casse, correction). NotFoundError si absent."""
        if quantity_delta == 0:
            raise ValidationError("quantity_delta must not be zero", field="quantity_delta")

        product = await self.product_service.apply_stock_delta(
            product_id, store_id, quantity_delta, enable_tracking=True
        )
        movement = StockMovement(
            store_id=store_id,
            product_id=product_id,
            quantity_delta=quantity_delta,
            reason=StockMovementReason.manual_adjustment.value,
            resulting_stock=product.current_stock,
            sale_id=None,
            created_by=user_id,
            note=note,
        )
        return await self.repo.create(movement)

    async def record_sale_movements(
        self,
        store_id: UUID,
        sale_id: UUID,
        items: list[tuple[UUID, int]],
        user_id: UUID | None,
    ) -> None:
        """Décrémente le stock et trace un mouvement par item vendu.

        Ne relance JAMAIS : un échec de traçabilité ne doit jamais faire échouer
        une vente (le stock ne bloque jamais une vente, décision produit actée).
        """
        for product_id, quantity in items:
            try:
                product = await self.product_service.apply_stock_delta(
                    product_id, store_id, -quantity, enable_tracking=False
                )
                movement = StockMovement(
                    store_id=store_id,
                    product_id=product_id,
                    quantity_delta=-quantity,
                    reason=StockMovementReason.sale.value,
                    resulting_stock=product.current_stock,
                    sale_id=sale_id,
                    created_by=user_id,
                    note=None,
                )
                await self.repo.create(movement)
            except Exception:
                logger.warning(
                    "stock_movement_recording_failed",
                    product_id=str(product_id),
                    sale_id=str(sale_id),
                )

    async def record_catalog_update(
        self,
        store_id: UUID,
        product_id: UUID,
        new_stock: int | None,
        user_id: UUID | None,
    ) -> StockMovement | None:
        """Traduit un changement direct de current_stock (PATCH produit / sync) en mouvement.

        No-op (aucun mouvement) si new_stock est inchangé par rapport à la valeur
        actuelle, pour préserver l'idempotence des retries PATCH/sync.
        """
        product = await self.product_service.get_by_id(product_id, store_id)
        old_stock = product.current_stock
        if old_stock == new_stock:
            return None

        if new_stock is None:
            await self.product_service.disable_stock_tracking(product_id, store_id)
            movement = StockMovement(
                store_id=store_id,
                product_id=product_id,
                quantity_delta=None,
                reason=StockMovementReason.catalog_update.value,
                resulting_stock=None,
                sale_id=None,
                created_by=user_id,
                note="Stock tracking disabled",
            )
            return await self.repo.create(movement)

        delta = new_stock - (old_stock or 0)
        updated = await self.product_service.apply_stock_delta(
            product_id, store_id, delta, enable_tracking=True
        )
        movement = StockMovement(
            store_id=store_id,
            product_id=product_id,
            quantity_delta=delta,
            reason=StockMovementReason.catalog_update.value,
            resulting_stock=updated.current_stock,
            sale_id=None,
            created_by=user_id,
            note=None,
        )
        return await self.repo.create(movement)

    async def list_movements(
        self,
        store_id: UUID,
        product_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> CursorPage[StockMovementResponse]:
        """Liste paginée de l'historique des mouvements de stock."""
        rows, has_more = await self.repo.list_movements(
            store_id=store_id, product_id=product_id, cursor=cursor, limit=limit
        )
        items = [StockMovementResponse.model_validate(m) for m in rows]
        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(
                {"id": str(last.id), "created_at": last.created_at.isoformat()}
            )
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)
