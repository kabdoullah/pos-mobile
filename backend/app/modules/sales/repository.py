"""Accès aux données du module sales."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import decode_cursor
from app.modules.sales.models import Sale, SaleItem


class _CursorData(TypedDict):
    id: UUID
    created_at: datetime


class _PaymentMethodRow(TypedDict):
    payment_method: str
    amount: Decimal
    count: int


class _TopProductRow(TypedDict):
    product_name: str
    quantity_sold: int
    revenue: Decimal


class DailySummaryResult(TypedDict):
    total_amount: Decimal
    sales_count: int
    by_payment_method: list[_PaymentMethodRow]
    top_products: list[_TopProductRow]


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


class SaleRepository:
    """Repository pour l'agrégat Sale + SaleItem."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, sale_id: UUID) -> Sale | None:
        stmt = select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_sale_atomic(self, sale: Sale, items: list[SaleItem]) -> Sale:
        """Insère la vente avec idempotence via ON CONFLICT DO NOTHING.

        Si l'id existe déjà (retry de sync), retourne la vente existante sans erreur.
        """
        stmt = (
            pg_insert(Sale)
            .values(
                id=sale.id,
                store_id=sale.store_id,
                total_amount=sale.total_amount,
                vat_amount=sale.vat_amount,
                payment_method=sale.payment_method,
                cash_amount=sale.cash_amount,
                mobile_money_amount=sale.mobile_money_amount,
                created_at=sale.created_at,
            )
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(Sale.id)
        )
        result = await self.db.execute(stmt)
        inserted_id = result.scalar_one_or_none()

        if inserted_id is None:
            existing = await self.get_by_id(sale.id)
            if existing is None:
                raise RuntimeError(f"Sale {sale.id} not found after conflict on insert")
            return existing

        for item in items:
            item.sale_id = sale.id
            item.store_id = sale.store_id
            self.db.add(item)

        await self.db.flush()

        # Re-SELECT pour récupérer receipt_number généré par le trigger BEFORE INSERT
        loaded = await self.get_by_id(sale.id)
        if loaded is None:
            raise RuntimeError(f"Sale {sale.id} not found after successful insert")
        return loaded

    async def list_sales(
        self,
        cursor: str | None = None,
        limit: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[Sale], bool]:
        """Liste les ventes avec pagination cursor-based.

        Tri par (created_at DESC, id DESC). Retourne (items, has_more).
        """
        stmt = select(Sale).options(selectinload(Sale.items))

        if date_from is not None:
            stmt = stmt.where(Sale.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Sale.created_at < date_to)

        if cursor:
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                stmt = stmt.where(
                    tuple_(Sale.created_at, Sale.id) < (parsed["created_at"], parsed["id"])
                )

        stmt = stmt.order_by(Sale.created_at.desc(), Sale.id.desc()).limit(limit + 1)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more

    async def list_sales_by_date_range(self, date_from: datetime, date_to: datetime) -> list[Sale]:
        """Variante non-paginée pour les résumés par période."""
        stmt = (
            select(Sale)
            .options(selectinload(Sale.items))
            .where(Sale.created_at >= date_from, Sale.created_at < date_to)
            .order_by(Sale.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_daily_summary(self, target_date: date) -> DailySummaryResult:
        """Agrégations SQL pour le résumé du jour.

        Africa/Abidjan est UTC+0 donc target_date 00:00 == UTC 00:00.
        """
        date_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
        date_end = date_start + timedelta(days=1)

        totals_stmt = select(
            func.coalesce(func.sum(Sale.total_amount), Decimal("0")).label("total_amount"),
            func.count(Sale.id).label("sales_count"),
        ).where(Sale.created_at >= date_start, Sale.created_at < date_end)
        totals = (await self.db.execute(totals_stmt)).one()

        by_pm_stmt = (
            select(
                Sale.payment_method.label("payment_method"),
                func.sum(Sale.total_amount).label("amount"),
                func.count(Sale.id).label("cnt"),
            )
            .where(Sale.created_at >= date_start, Sale.created_at < date_end)
            .group_by(Sale.payment_method)
        )
        by_pm_rows = (await self.db.execute(by_pm_stmt)).all()

        top_stmt = (
            select(
                SaleItem.product_name_at_sale.label("product_name"),
                func.sum(SaleItem.quantity).label("quantity_sold"),
                func.sum(SaleItem.line_total).label("revenue"),
            )
            .join(Sale, SaleItem.sale_id == Sale.id)
            .where(Sale.created_at >= date_start, Sale.created_at < date_end)
            .group_by(SaleItem.product_name_at_sale)
            .order_by(func.sum(SaleItem.quantity).desc())
            .limit(5)
        )
        top_rows = (await self.db.execute(top_stmt)).all()

        return DailySummaryResult(
            total_amount=totals.total_amount,
            sales_count=totals.sales_count,
            by_payment_method=[
                _PaymentMethodRow(
                    payment_method=row.payment_method,
                    amount=row.amount,
                    count=row.cnt,
                )
                for row in by_pm_rows
            ],
            top_products=[
                _TopProductRow(
                    product_name=row.product_name,
                    quantity_sold=row.quantity_sold,
                    revenue=row.revenue,
                )
                for row in top_rows
            ],
        )
