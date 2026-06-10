"""Logique métier du module sync."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.catalog.models import Product
from app.modules.catalog.repository import ProductRepository
from app.modules.catalog.schemas import ProductResponse
from app.modules.sales.schemas import SaleResponse
from app.modules.sales.service import SaleService
from app.modules.sync.repository import SyncRepository
from app.modules.sync.schemas import (
    ProductSyncRequest,
    ProductSyncResponse,
    ProductSyncStatus,
    SalesBatchSyncRequest,
    SalesBatchSyncResponse,
    SaleSyncResult,
    SaleSyncResultStatus,
    SyncChangesResponse,
)

if TYPE_CHECKING:
    from app.modules.sales.models import Sale

_SYNC_TOLERANCE_MS = 1

logger = structlog.get_logger()


def _client_wins(client_ts: datetime, server_ts: datetime) -> bool:
    """True si le client a un état strictement plus récent (tolérance 1 ms)."""
    return (client_ts - server_ts).total_seconds() * 1000 > _SYNC_TOLERANCE_MS


def _ts_equal(client_ts: datetime, server_ts: datetime) -> bool:
    """True si les deux timestamps sont à moins de 1 ms l'un de l'autre."""
    return abs((client_ts - server_ts).total_seconds() * 1000) <= _SYNC_TOLERANCE_MS


class SyncService:
    """Service métier de la synchronisation bidirectionnelle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.product_repo = ProductRepository(db)
        self.sale_service = SaleService(db)
        self.sync_repo = SyncRepository(db)

    async def sync_sales_batch(
        self, store_id: UUID, payload: SalesBatchSyncRequest
    ) -> SalesBatchSyncResponse:
        """Sync best-effort d'un lot de ventes.

        Chaque vente est insérée dans son propre SAVEPOINT pour que l'échec
        d'une vente n'annule pas les autres.
        """
        results: list[SaleSyncResult] = []
        for sale_payload in payload.sales:
            try:
                async with self.db.begin_nested():
                    sale, was_created = await self.sale_service.create_sale(store_id, sale_payload)
                status = (
                    SaleSyncResultStatus.created
                    if was_created
                    else SaleSyncResultStatus.already_exists
                )
                results.append(
                    SaleSyncResult(id=sale.id, status=status, receipt_number=sale.receipt_number)
                )
            except Exception as exc:
                logger.warning(
                    "sale_sync_failed",
                    sale_id=str(sale_payload.id),
                    error=str(exc),
                )
                results.append(
                    SaleSyncResult(
                        id=sale_payload.id,
                        status=SaleSyncResultStatus.failed,
                        error=str(exc),
                    )
                )
        return SalesBatchSyncResponse(processed=len(results), results=results)

    async def _apply_product_changes(
        self, product: Product, payload: ProductSyncRequest
    ) -> tuple[ProductSyncResponse, int]:
        """Applique l'état client sur un produit existant (appelé quand client gagne)."""
        if payload.deleted:
            await self.product_repo.soft_delete(product)
            return ProductSyncResponse(id=payload.id, status=ProductSyncStatus.deleted), 200

        server_deleted = product.deleted_at is not None
        if payload.barcode is not None:
            conflict = await self.product_repo.get_active_by_barcode_excluding(
                payload.barcode, payload.id
            )
            if conflict is not None:
                return (
                    ProductSyncResponse(
                        id=payload.id,
                        status=ProductSyncStatus.conflict,
                        server_state=ProductResponse.model_validate(product)
                        if not server_deleted
                        else None,
                    ),
                    409,
                )

        updates: dict[str, Any] = {
            "name": payload.name,
            "barcode": payload.barcode,
            "unit_price": payload.unit_price,
            "current_stock": payload.current_stock,
            "deleted_at": None,
        }
        updated = await self.product_repo.update(product, updates)
        return (
            ProductSyncResponse(
                id=updated.id,
                status=ProductSyncStatus.updated,
                server_state=ProductResponse.model_validate(updated),
            ),
            200,
        )

    async def sync_product_state(
        self, store_id: UUID, payload: ProductSyncRequest
    ) -> tuple[ProductSyncResponse, int]:
        """Applique l'état produit du client selon la règle last-write-wins avec détection de conflit.

        Retourne (response, http_status_code).
        """
        product = await self.product_repo.get_by_id_including_deleted(payload.id)

        # CAS 1 : produit inexistant sur le serveur
        if product is None:
            if payload.deleted:
                return ProductSyncResponse(id=payload.id, status=ProductSyncStatus.no_change), 200
            if payload.barcode is not None:
                conflict = await self.product_repo.get_active_by_barcode_excluding(
                    payload.barcode, payload.id
                )
                if conflict is not None:
                    return (
                        ProductSyncResponse(id=payload.id, status=ProductSyncStatus.conflict),
                        409,
                    )
            created = await self.product_repo.create(
                Product(
                    id=payload.id,
                    store_id=store_id,
                    name=payload.name,
                    barcode=payload.barcode,
                    unit_price=payload.unit_price,
                    current_stock=payload.current_stock,
                    updated_at=payload.client_updated_at,
                )
            )
            return (
                ProductSyncResponse(
                    id=created.id,
                    status=ProductSyncStatus.created,
                    server_state=ProductResponse.model_validate(created),
                ),
                201,
            )

        # CAS 2 & 3 : produit existant
        server_deleted = product.deleted_at is not None
        if (server_deleted and payload.deleted) or _ts_equal(
            payload.client_updated_at, product.updated_at
        ):
            return ProductSyncResponse(id=payload.id, status=ProductSyncStatus.no_change), 200

        if not _client_wins(payload.client_updated_at, product.updated_at):
            return (
                ProductSyncResponse(
                    id=payload.id,
                    status=ProductSyncStatus.conflict,
                    server_state=ProductResponse.model_validate(product)
                    if not server_deleted
                    else None,
                ),
                409,
            )

        return await self._apply_product_changes(product, payload)

    async def get_changes(
        self,
        store_id: UUID,
        since: datetime | None,
        cursor: str | None,
        limit: int,
    ) -> SyncChangesResponse:
        """Retourne les changements depuis `since`, paginés.

        Ordre stable : produits en premier (tri updated_at ASC), puis ventes (tri synced_at ASC).
        Le cursor encode la phase courante et la position dans cette phase.
        """
        server_time = datetime.now(UTC)

        phase = "products"
        cursor_after_id: UUID | None = None
        cursor_after_ts: datetime | None = None

        if cursor is not None:
            raw = decode_cursor(cursor)
            if raw is not None:
                try:
                    phase = str(raw.get("phase", "products"))
                    raw_id = raw.get("id")
                    raw_ts = raw.get("ts")
                    if raw_id is not None and raw_ts is not None:
                        cursor_after_id = UUID(str(raw_id))
                        cursor_after_ts = datetime.fromisoformat(str(raw_ts))
                except (KeyError, ValueError):
                    pass

        products: list[Product] = []
        sales: list[Sale] = []
        has_more = False
        next_cursor: str | None = None

        if phase == "products":
            products, products_has_more = await self.sync_repo.list_changed_products(
                store_id=store_id,
                since=since,
                limit=limit,
                cursor_after_id=cursor_after_id,
                cursor_after_updated_at=cursor_after_ts,
            )
            if products_has_more:
                last_product = products[-1]
                has_more = True
                next_cursor = encode_cursor(
                    {
                        "phase": "products",
                        "id": str(last_product.id),
                        "ts": last_product.updated_at.isoformat(),
                    }
                )
            else:
                remaining = limit - len(products)
                if remaining == 0:
                    # Produits remplissent exactement le limit : on ne sait pas s'il y a des ventes.
                    # On émet un cursor de transition vers la phase "sales" pour le prochain appel.
                    has_more = True
                    next_cursor = encode_cursor({"phase": "sales"})
                else:
                    sales, sales_has_more = await self.sync_repo.list_changed_sales(
                        store_id=store_id,
                        since=since,
                        limit=remaining,
                        cursor_after_id=None,
                        cursor_after_synced_at=None,
                    )
                    if sales_has_more:
                        last_sale = sales[-1]
                        has_more = True
                        next_cursor = encode_cursor(
                            {
                                "phase": "sales",
                                "id": str(last_sale.id),
                                "ts": last_sale.synced_at.isoformat(),
                            }
                        )

        else:  # phase == "sales"
            sales, sales_has_more = await self.sync_repo.list_changed_sales(
                store_id=store_id,
                since=since,
                limit=limit,
                cursor_after_id=cursor_after_id,
                cursor_after_synced_at=cursor_after_ts,
            )
            if sales_has_more:
                last_sale = sales[-1]
                has_more = True
                next_cursor = encode_cursor(
                    {
                        "phase": "sales",
                        "id": str(last_sale.id),
                        "ts": last_sale.synced_at.isoformat(),
                    }
                )

        return SyncChangesResponse(
            products=[ProductResponse.model_validate(p) for p in products],
            sales=[SaleResponse.model_validate(s) for s in sales],
            next_cursor=next_cursor,
            has_more=has_more,
            server_time=server_time,
        )
