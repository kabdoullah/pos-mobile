"""Routes du module inventory."""

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.core.pagination import CursorPage
from app.modules.inventory.schemas import ManualStockAdjustmentCreate, StockMovementResponse
from app.modules.inventory.service import InventoryService

router = APIRouter()


@router.post(
    "/movements",
    response_model=StockMovementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ajustement manuel du stock",
)
async def create_manual_adjustment(
    payload: ManualStockAdjustmentCreate,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> StockMovementResponse:
    """Enregistre un ajustement manuel (réception, casse, correction d'inventaire).

    Le stock peut devenir négatif : aucun blocage sur stock insuffisant.
    """
    service = InventoryService(db)
    movement = await service.record_manual_adjustment(
        store_id, payload.product_id, payload.quantity_delta, payload.note, user_id
    )
    return StockMovementResponse.model_validate(movement)


@router.get(
    "/movements",
    response_model=CursorPage[StockMovementResponse],
    summary="Historique des mouvements de stock",
)
async def list_movements(
    db: TenantDbSession,
    store_id: CurrentStoreId,
    product_id: UUID | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> CursorPage[StockMovementResponse]:
    """Liste paginée de l'historique des mouvements, filtrable par produit."""
    return await InventoryService(db).list_movements(
        store_id=store_id, product_id=product_id, cursor=cursor, limit=limit
    )
