"""Logique métier du module sync."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.catalog.models import Category, Product
from app.modules.catalog.repository import CategoryRepository, ProductRepository
from app.modules.catalog.schemas import CategoryResponse, ProductResponse
from app.modules.catalog.service import CategoryService
from app.modules.inventory.service import InventoryService
from app.modules.sales.schemas import SaleResponse
from app.modules.sales.service import SaleService
from app.modules.sync.repository import SyncRepository
from app.modules.sync.schemas import (
    CategorySyncRequest,
    CategorySyncResponse,
    ProductSyncRequest,
    ProductSyncResponse,
    ProductSyncStatus,
    SalesBatchSyncRequest,
    SalesBatchSyncResponse,
    SaleSyncResult,
    SaleSyncResultStatus,
    SyncChangesResponse,
)

_SYNC_TOLERANCE_MS = 1

# Ordre du pull : une catégorie arrive toujours avant ses produits.
_PHASES = ("categories", "products", "sales")


def _phase_ts(phase: str, row: Any) -> datetime:
    """Horodatage de tri d'une ligne selon sa phase (synced_at pour les ventes)."""
    ts: datetime = row.synced_at if phase == "sales" else row.updated_at
    return ts


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
        self.category_repo = CategoryRepository(db)
        self.category_service = CategoryService(db)
        self.sale_service = SaleService(db)
        self.sync_repo = SyncRepository(db)
        self.inventory_service = InventoryService(db)

    async def sync_sales_batch(
        self, store_id: UUID, payload: SalesBatchSyncRequest, user_id: UUID | None = None
    ) -> SalesBatchSyncResponse:
        """Sync best-effort d'un lot de ventes.

        Chaque vente est insérée dans son propre SAVEPOINT pour que l'échec
        d'une vente n'annule pas les autres.
        """
        results: list[SaleSyncResult] = []
        for sale_payload in payload.sales:
            try:
                async with self.db.begin_nested():
                    sale, was_created = await self.sale_service.create_sale(
                        store_id, sale_payload, user_id
                    )
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
        self, product: Product, payload: ProductSyncRequest, user_id: UUID | None
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

        # current_stock est retiré des updates génériques : appliqué séparément via
        # InventoryService pour que chaque changement soit tracé dans stock_movements.
        updates: dict[str, Any] = {
            "name": payload.name,
            "barcode": payload.barcode,
            "selling_price": payload.selling_price,
            "min_stock": payload.min_stock,
            "deleted_at": None,
        }
        # Champ absent (ancienne app) : on ne touche pas au prix d'achat.
        if "purchase_price" in payload.model_fields_set:
            updates["purchase_price"] = payload.purchase_price
        # Champ absent (ancienne app) : on ne touche pas à la catégorie.
        if "category_id" in payload.model_fields_set:
            updates["category_id"] = await self.category_service.resolve_for_product(
                product.store_id, payload.category_id
            )
        updated = await self.product_repo.update(product, updates)
        await self.inventory_service.record_catalog_update(
            updated.store_id, updated.id, payload.current_stock, user_id
        )
        return (
            ProductSyncResponse(
                id=updated.id,
                status=ProductSyncStatus.updated,
                server_state=ProductResponse.model_validate(updated),
            ),
            200,
        )

    async def sync_product_state(
        self, store_id: UUID, payload: ProductSyncRequest, user_id: UUID | None = None
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
            category_id = await self.category_service.resolve_for_product(
                store_id, payload.category_id
            )
            created = await self.product_repo.create(
                Product(
                    id=payload.id,
                    store_id=store_id,
                    name=payload.name,
                    barcode=payload.barcode,
                    selling_price=payload.selling_price,
                    purchase_price=payload.purchase_price,
                    current_stock=None,
                    min_stock=payload.min_stock,
                    category_id=category_id,
                    updated_at=payload.client_updated_at,
                )
            )
            if payload.current_stock is not None:
                await self.inventory_service.record_catalog_update(
                    store_id, created.id, payload.current_stock, user_id
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

        return await self._apply_product_changes(product, payload, user_id)

    def _category_conflict(
        self, category_id: UUID, current: Category | None
    ) -> tuple[CategorySyncResponse, int]:
        """409 avec l'état serveur (s'il existe et n'est pas supprimé)."""
        state = (
            CategoryResponse.model_validate(current)
            if current is not None and current.deleted_at is None
            else None
        )
        return (
            CategorySyncResponse(
                id=category_id, status=ProductSyncStatus.conflict, server_state=state
            ),
            409,
        )

    async def _create_category_from_client(
        self, store_id: UUID, payload: CategorySyncRequest
    ) -> tuple[CategorySyncResponse, int]:
        """Catégorie inconnue du serveur : création (ou rien si déjà supprimée)."""
        if payload.deleted:
            return CategorySyncResponse(id=payload.id, status=ProductSyncStatus.no_change), 200
        if await self.category_repo.get_active_by_name_excluding(
            payload.name, store_id, payload.id
        ):
            return self._category_conflict(payload.id, None)
        created = await self.category_repo.create(
            Category(
                id=payload.id,
                store_id=store_id,
                name=payload.name,
                updated_at=payload.client_updated_at,
            )
        )
        return (
            CategorySyncResponse(
                id=created.id,
                status=ProductSyncStatus.created,
                server_state=CategoryResponse.model_validate(created),
            ),
            201,
        )

    async def _apply_category_changes(
        self, store_id: UUID, category: Category, payload: CategorySyncRequest
    ) -> tuple[CategorySyncResponse, int]:
        """Applique l'état client sur une catégorie existante (le client gagne)."""
        if payload.deleted:
            await self.category_repo.soft_delete_and_detach_products(category)
            return CategorySyncResponse(id=payload.id, status=ProductSyncStatus.deleted), 200
        if await self.category_repo.get_active_by_name_excluding(
            payload.name, store_id, payload.id
        ):
            return self._category_conflict(payload.id, category)
        updated = await self.category_repo.update(
            category, {"name": payload.name, "deleted_at": None}
        )
        return (
            CategorySyncResponse(
                id=updated.id,
                status=ProductSyncStatus.updated,
                server_state=CategoryResponse.model_validate(updated),
            ),
            200,
        )

    async def sync_category_state(
        self, store_id: UUID, payload: CategorySyncRequest
    ) -> tuple[CategorySyncResponse, int]:
        """Applique l'état catégorie du client (last-write-wins, comme les produits).

        Conflit (409) si l'état serveur est plus récent, ou si une autre
        catégorie active porte déjà ce nom. Retourne (response, http_status_code).
        """
        category = await self.category_repo.get_by_id_including_deleted(payload.id)
        if category is None:
            return await self._create_category_from_client(store_id, payload)

        server_deleted = category.deleted_at is not None
        if (server_deleted and payload.deleted) or _ts_equal(
            payload.client_updated_at, category.updated_at
        ):
            return CategorySyncResponse(id=payload.id, status=ProductSyncStatus.no_change), 200

        if not _client_wins(payload.client_updated_at, category.updated_at):
            return self._category_conflict(payload.id, category)

        return await self._apply_category_changes(store_id, category, payload)

    async def get_changes(
        self,
        store_id: UUID,
        since: datetime | None,
        cursor: str | None,
        limit: int,
    ) -> SyncChangesResponse:
        """Retourne les changements depuis `since`, paginés.

        Phases dans un ordre stable : catégories puis produits (tri updated_at
        ASC), puis ventes (tri synced_at ASC). Les catégories passent d'abord pour
        qu'un produit n'arrive jamais avant sa catégorie. Le cursor encode la
        phase courante et la position dans cette phase ; un cursor émis avant
        l'ajout des catégories (phase « products » ou « sales ») reste valide.
        """
        server_time = datetime.now(UTC)

        phase = _PHASES[0]
        cursor_after_id: UUID | None = None
        cursor_after_ts: datetime | None = None

        if cursor is not None:
            raw = decode_cursor(cursor)
            if raw is not None:
                try:
                    raw_phase = str(raw.get("phase", _PHASES[0]))
                    phase = raw_phase if raw_phase in _PHASES else _PHASES[0]
                    raw_id = raw.get("id")
                    raw_ts = raw.get("ts")
                    if raw_id is not None and raw_ts is not None:
                        cursor_after_id = UUID(str(raw_id))
                        cursor_after_ts = datetime.fromisoformat(str(raw_ts))
                except (KeyError, ValueError):
                    pass

        rows: dict[str, list[Any]] = {name: [] for name in _PHASES}
        has_more = False
        next_cursor: str | None = None
        remaining = limit

        for index in range(_PHASES.index(phase), len(_PHASES)):
            name = _PHASES[index]
            # La position du cursor ne vaut que pour la phase où il a été émis.
            after_id = cursor_after_id if name == phase else None
            after_ts = cursor_after_ts if name == phase else None
            items, phase_has_more = await self._list_phase(
                name, store_id, since, remaining, after_id, after_ts
            )
            rows[name] = items

            if phase_has_more:
                last = items[-1]
                has_more = True
                next_cursor = encode_cursor(
                    {"phase": name, "id": str(last.id), "ts": _phase_ts(name, last).isoformat()}
                )
                break

            remaining -= len(items)
            if remaining == 0:
                # La page est pleine pile à la fin de cette phase : on ne sait pas
                # si la suivante a des données. Cursor de transition vers elle.
                if index + 1 < len(_PHASES):
                    has_more = True
                    next_cursor = encode_cursor({"phase": _PHASES[index + 1]})
                break

        return SyncChangesResponse(
            categories=[CategoryResponse.model_validate(c) for c in rows["categories"]],
            products=[ProductResponse.model_validate(p) for p in rows["products"]],
            sales=[SaleResponse.model_validate(s) for s in rows["sales"]],
            next_cursor=next_cursor,
            has_more=has_more,
            server_time=server_time,
        )

    async def _list_phase(
        self,
        phase: str,
        store_id: UUID,
        since: datetime | None,
        limit: int,
        after_id: UUID | None,
        after_ts: datetime | None,
    ) -> tuple[list[Any], bool]:
        """Lit une page d'une phase du pull."""
        if phase == "categories":
            categories, more = await self.sync_repo.list_changed_categories(
                store_id=store_id,
                since=since,
                limit=limit,
                cursor_after_id=after_id,
                cursor_after_updated_at=after_ts,
            )
            return list(categories), more
        if phase == "products":
            products, more = await self.sync_repo.list_changed_products(
                store_id=store_id,
                since=since,
                limit=limit,
                cursor_after_id=after_id,
                cursor_after_updated_at=after_ts,
            )
            return list(products), more
        sales, more = await self.sync_repo.list_changed_sales(
            store_id=store_id,
            since=since,
            limit=limit,
            cursor_after_id=after_id,
            cursor_after_synced_at=after_ts,
        )
        return list(sales), more
