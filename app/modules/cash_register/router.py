"""Routes du module cash_register (ADR-0015, spec §5)."""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.modules.cash_register.schemas import (
    CashSessionDetailResponse,
    CashSessionOpen,
    CashSessionPage,
    CashSessionResponse,
)
from app.modules.cash_register.service import CashSessionService

router = APIRouter()


@router.post(
    "",
    response_model=CashSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"description": "Retry : session déjà enregistrée, même contenu"},
        status.HTTP_409_CONFLICT: {
            "description": "CASH_SESSION_ALREADY_OPEN ou IDEMPOTENCY_CONFLICT"
        },
    },
    summary="Ouvrir une session de caisse",
)
async def open_cash_session(
    payload: CashSessionOpen,
    response: Response,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> CashSessionResponse:
    """Ouvre la caisse d'un appareil. **201** : créée ; **200** : retry du même `id`."""
    session, created = await CashSessionService(db).open(store_id, user_id, payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return CashSessionResponse.model_validate(session)


# IMPORTANT : route statique avant /{session_id}.
@router.get(
    "/active",
    response_model=CashSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Session ouverte d'un appareil",
)
async def get_active_cash_session(
    db: TenantDbSession,
    _store_id: CurrentStoreId,
    _user_id: CurrentUserId,
    device_id: UUID = Query(...),
) -> CashSessionDetailResponse:
    """Session ouverte de l'appareil, avec résumé et mouvements. 404 si aucune."""
    return await CashSessionService(db).get_active(device_id)


@router.get(
    "",
    response_model=CashSessionPage,
    status_code=status.HTTP_200_OK,
    summary="Historique des sessions de caisse",
)
async def list_cash_sessions(
    db: TenantDbSession,
    _store_id: CurrentStoreId,
    _user_id: CurrentUserId,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    device_id: UUID | None = Query(None),
) -> CashSessionPage:
    """Sessions de la boutique (ou d'un appareil), triées par ouverture décroissante."""
    return await CashSessionService(db).list_page(device_id, cursor, limit)


@router.get(
    "/{session_id}",
    response_model=CashSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Détail d'une session de caisse",
)
async def get_cash_session(
    session_id: UUID,
    db: TenantDbSession,
    _store_id: CurrentStoreId,
    _user_id: CurrentUserId,
) -> CashSessionDetailResponse:
    """Session, résumé et mouvements. 404 si inconnue ou d'une autre boutique."""
    return await CashSessionService(db).get_detail(session_id)
