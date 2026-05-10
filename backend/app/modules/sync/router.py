"""Routes du module sync."""

from datetime import datetime

from fastapi import APIRouter, Query, Response, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId
from app.core.exceptions import ValidationError
from app.modules.sync.schemas import (
    ProductSyncRequest,
    ProductSyncResponse,
    SalesBatchSyncRequest,
    SalesBatchSyncResponse,
    SyncChangesResponse,
)
from app.modules.sync.service import SyncService

router = APIRouter()


@router.post(
    "/sales",
    response_model=SalesBatchSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Push de ventes en mode best-effort, idempotent par UUID",
)
async def sync_sales_batch(
    payload: SalesBatchSyncRequest,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> SalesBatchSyncResponse:
    """Push de ventes en mode best-effort, idempotent par UUID.

    Insère un lot de ventes (max 50). Une vente déjà présente (même UUID) retourne
    `already_exists` sans erreur. Les échecs sont isolés par SAVEPOINT : une vente
    invalide n'annule pas les autres. Retourne toujours 200.
    """
    return await SyncService(db).sync_sales_batch(store_id, payload)


@router.put(
    "/products",
    response_model=ProductSyncResponse,
    responses={
        status.HTTP_200_OK: {"description": "updated / no_change / deleted"},
        status.HTTP_201_CREATED: {"description": "created — produit inexistant côté serveur"},
        status.HTTP_409_CONFLICT: {
            "description": "conflict — état serveur plus récent, server_state retourné"
        },
    },
    summary="Synchroniser l'état d'un produit (upsert last-write-wins)",
)
async def sync_product(
    payload: ProductSyncRequest,
    response: Response,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> ProductSyncResponse:
    """Applique l'état produit du client selon la règle last-write-wins.

    - **201** : produit créé (UUID inconnu du serveur)
    - **200** : mis à jour, supprimé (soft-delete), ou aucun changement nécessaire
    - **409** : conflit — le serveur a un état plus récent ; `server_state` contient
      l'état serveur actuel pour que le client puisse fusionner manuellement
    """
    result, http_status = await SyncService(db).sync_product_state(store_id, payload)
    response.status_code = http_status
    return result


@router.get(
    "/changes",
    response_model=SyncChangesResponse,
    summary="Pull des changements depuis une date (sync initiale ou incrémentale)",
)
async def get_changes(
    db: TenantDbSession,
    _store_id: CurrentStoreId,
    since: datetime | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
) -> SyncChangesResponse:
    """Retourne les produits et ventes modifiés depuis `since`.

    - `since` absent : retourne l'intégralité de l'historique (sync initiale)
    - `since` présent : doit être timezone-aware (ISO 8601 avec offset, ex. `2024-01-01T00:00:00Z`)
    - Paginer via `next_cursor` jusqu'à `has_more=False`
    - Produits triés par `updated_at ASC`, ventes par `synced_at ASC`
    """
    if since is not None and since.tzinfo is None:
        raise ValidationError("since must be timezone-aware")
    return await SyncService(db).get_changes(since=since, cursor=cursor, limit=limit)
