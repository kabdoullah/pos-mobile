"""Logique métier du module returns (ADR-0010)."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.catalog.service import ProductService
from app.modules.inventory.service import InventoryService
from app.modules.returns.exceptions import ReturnRejectedError, ReturnRejectionCode
from app.modules.returns.models import SaleReturn, SaleReturnItem
from app.modules.returns.refund import allocate_paid_amounts, refund_for
from app.modules.returns.repository import SaleReturnRepository
from app.modules.returns.schemas import ItemCondition, SaleReturnCreate
from app.modules.sales.service import SaleService


class ReturnService:
    """Service métier des retours clients."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SaleReturnRepository(db)
        self.sale_service = SaleService(db)
        self.product_service = ProductService(db)
        self.inventory_service = InventoryService(db)

    async def create_return(
        self, store_id: UUID, payload: SaleReturnCreate, user_id: UUID | None = None
    ) -> tuple[SaleReturn, bool]:
        """Enregistre un retour de manière idempotente et atomique.

        Retourne (retour, was_created) ; was_created=False si l'id existait déjà.
        La vente est verrouillée pendant la transaction : deux retours concurrents
        d'une même vente sont sérialisés, le second voit les quantités du premier.
        Lève ReturnRejectedError si le retour ne pourra jamais être accepté.
        """
        existing = await self.repo.get_by_id(payload.id)
        if existing is not None:
            return existing, False

        sale = await self.sale_service.get_sale_for_update(payload.sale_id)
        if sale is None:
            raise ReturnRejectedError(ReturnRejectionCode.sale_not_found, "Sale not found.")

        # Le même retour a pu être inséré pendant l'attente du verrou.
        existing = await self.repo.get_by_id(payload.id)
        if existing is not None:
            return existing, False

        sold = {item.id: item for item in sale.items}
        returned = await self.repo.returned_quantities(sale.id)
        paid = allocate_paid_amounts(
            [(item.id, item.line_total) for item in sale.items], sale.total_amount
        )

        lines: list[SaleReturnItem] = []
        restock: list[tuple[UUID, int]] = []
        for line in payload.items:
            sale_item = sold.get(line.sale_item_id)
            if sale_item is None:
                raise ReturnRejectedError(
                    ReturnRejectionCode.item_not_in_sale,
                    f"Sale item {line.sale_item_id} does not belong to sale {sale.id}.",
                )
            already = returned.get(sale_item.id, 0)
            if already + line.quantity > sale_item.quantity:
                raise ReturnRejectedError(
                    ReturnRejectionCode.quantity_exceeded,
                    f"Sale item {sale_item.id}: {line.quantity} requested, "
                    f"{sale_item.quantity - already} returnable.",
                )
            expected = Decimal(
                refund_for(paid[sale_item.id], sale_item.quantity, already, line.quantity)
            )
            if line.refund_amount != expected:
                raise ReturnRejectedError(
                    ReturnRejectionCode.amount_mismatch,
                    f"Sale item {sale_item.id}: refund {line.refund_amount} != expected {expected}.",
                )

            restocked = line.condition == ItemCondition.resellable and await self._is_active(
                sale_item.product_id, store_id
            )
            if restocked and sale_item.product_id is not None:
                restock.append((sale_item.product_id, line.quantity))
            lines.append(
                SaleReturnItem(
                    id=line.id,
                    store_id=store_id,
                    sale_item_id=sale_item.id,
                    product_id=sale_item.product_id,
                    quantity=line.quantity,
                    condition=line.condition.value,
                    restocked=restocked,
                    refund_amount=expected,
                )
            )

        sale_return = SaleReturn(
            id=payload.id,
            store_id=store_id,
            sale_id=sale.id,
            reason=payload.reason.value,
            note=payload.note,
            refund_method=payload.refund_method.value,
            refund_amount=payload.refund_amount,
            created_at=payload.created_at,
            created_by=user_id,
            items=lines,
        )
        created = await self.repo.create(sale_return)
        await self.inventory_service.record_return_movements(store_id, created.id, restock, user_id)
        return created, True

    async def _is_active(self, product_id: UUID | None, store_id: UUID) -> bool:
        """True si le produit existe encore (ni supprimé ni anonymisé)."""
        if product_id is None:
            return False
        try:
            await self.product_service.get_by_id(product_id, store_id)
        except NotFoundError:
            return False
        return True

    async def list_changed(
        self,
        store_id: UUID,
        since: datetime | None,
        limit: int,
        cursor_after_id: UUID | None,
        cursor_after_synced_at: datetime | None,
    ) -> tuple[list[SaleReturn], bool]:
        """Retours syncés depuis `since`, pour le pull /sync/changes."""
        return await self.repo.list_changed(
            store_id, since, limit, cursor_after_id, cursor_after_synced_at
        )
