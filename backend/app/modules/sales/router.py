"""Routes du module sales."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId
from app.core.pagination import CursorPage
from app.modules.sales.schemas import DailySalesSummary, SaleCreate, SaleResponse
from app.modules.sales.service import SaleService

router = APIRouter()


@router.post(
    "",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enregistrer une vente",
)
async def create_sale(
    payload: SaleCreate,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> SaleResponse:
    """Enregistre une vente. Idempotent : si l'id existe déjà, retourne la vente existante."""
    sale, _ = await SaleService(db).create_sale(store_id, payload)
    return SaleResponse.model_validate(sale)


@router.get(
    "",
    response_model=CursorPage[SaleResponse],
    summary="Lister les ventes",
)
async def list_sales(
    db: TenantDbSession,
    store_id: CurrentStoreId,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
) -> CursorPage[SaleResponse]:
    """Liste paginée des ventes de la boutique, triées par date décroissante."""
    return await SaleService(db).list_sales(
        store_id=store_id, cursor=cursor, limit=limit, date_from=date_from, date_to=date_to
    )


# IMPORTANT : route statique avant /{sale_id} pour éviter que FastAPI
# tente de parser "today" comme un UUID.
@router.get(
    "/today/summary",
    response_model=DailySalesSummary,
    summary="Résumé du jour",
)
async def get_today_summary(
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> DailySalesSummary:
    """Résumé agrégé des ventes du jour (total, par moyen de paiement, top produits)."""
    return await SaleService(db).get_today_summary(store_id=store_id)


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Récupérer une vente",
)
async def get_sale(
    sale_id: UUID,
    db: TenantDbSession,
    _store_id: CurrentStoreId,
) -> SaleResponse:
    """Retourne une vente par son id. 404 si introuvable."""
    sale = await SaleService(db).get_sale(sale_id)
    return SaleResponse.model_validate(sale)
