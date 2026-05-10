"""Logique métier du module sales."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import CursorPage, encode_cursor
from app.modules.catalog.repository import ProductRepository
from app.modules.sales.models import Sale, SaleItem
from app.modules.sales.repository import SaleRepository
from app.modules.sales.schemas import (
    DailySalesSummary,
    PaymentMethodSummary,
    SaleCreate,
    SaleResponse,
    TopProduct,
)

_TZ_ABIDJAN = ZoneInfo("Africa/Abidjan")

logger = structlog.get_logger()


class SaleService:
    """Service métier de la gestion des ventes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = SaleRepository(db)
        self.product_repo = ProductRepository(db)

    async def create_sale(self, store_id: UUID, payload: SaleCreate) -> Sale:
        """Crée une vente de manière idempotente.

        Si l'id existe déjà, retourne la vente existante sans erreur (sync retry).
        Si un product_id n'existe plus côté serveur, forçe product_id=NULL
        mais conserve le snapshot (nom + prix) tel qu'envoyé par le client.
        """
        existing = await self.repo.get_by_id(payload.id)
        if existing is not None:
            return existing

        items: list[SaleItem] = []
        for item_payload in payload.items:
            resolved_product_id: UUID | None = item_payload.product_id
            if item_payload.product_id is not None:
                product = await self.product_repo.get_active_by_id(item_payload.product_id)
                if product is None:
                    logger.warning(
                        "Product referenced in sale no longer exists, setting product_id to NULL",
                        product_id=str(item_payload.product_id),
                        sale_id=str(payload.id),
                    )
                    resolved_product_id = None

            items.append(
                SaleItem(
                    product_id=resolved_product_id,
                    product_name_at_sale=item_payload.product_name_at_sale,
                    unit_price_at_sale=item_payload.unit_price_at_sale,
                    quantity=item_payload.quantity,
                    line_total=item_payload.line_total,
                )
            )

        sale = Sale(
            id=payload.id,
            store_id=store_id,
            total_amount=payload.total_amount,
            vat_amount=payload.vat_amount,
            payment_method=payload.payment_method.value,
            cash_amount=payload.cash_amount,
            mobile_money_amount=payload.mobile_money_amount,
            created_at=payload.created_at,
        )

        return await self.repo.create_sale_atomic(sale, items)

    async def get_sale(self, sale_id: UUID) -> Sale:
        """Retourne une vente par id ou lève NotFoundError."""
        sale = await self.repo.get_by_id(sale_id)
        if sale is None:
            raise NotFoundError("Sale not found.")
        return sale

    async def list_sales(
        self,
        cursor: str | None,
        limit: int,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> CursorPage[SaleResponse]:
        """Liste paginée des ventes de la boutique."""
        rows, has_more = await self.repo.list_sales(
            cursor=cursor, limit=limit, date_from=date_from, date_to=date_to
        )
        items = [SaleResponse.model_validate(s) for s in rows]
        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(
                {"id": str(last.id), "created_at": last.created_at.isoformat()}
            )
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def get_today_summary(self) -> DailySalesSummary:
        """Résumé des ventes du jour dans le fuseau Africa/Abidjan."""
        today = datetime.now(_TZ_ABIDJAN).date()
        raw = await self.repo.get_daily_summary(today)

        by_payment_method = {
            row["payment_method"]: PaymentMethodSummary(
                amount=row["amount"],
                count=row["count"],
            )
            for row in raw["by_payment_method"]
        }

        top_products = [
            TopProduct(
                product_name=row["product_name"],
                quantity_sold=row["quantity_sold"],
                revenue=row["revenue"],
            )
            for row in raw["top_products"]
        ]

        return DailySalesSummary(
            date=today,
            total_amount=raw["total_amount"],
            sales_count=raw["sales_count"],
            by_payment_method=by_payment_method,
            top_products=top_products,
        )
