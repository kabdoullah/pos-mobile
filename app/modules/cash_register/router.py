"""Routes du module cash_register (ADR-0015, spec §5)."""

from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.modules.cash_register.schemas import (
    CashMovementCreate,
    CashMovementResponse,
    CashSessionClose,
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


@router.post(
    "/{session_id}/movements",
    response_model=CashMovementResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_200_OK: {"description": "Retry : mouvement déjà enregistré, même contenu"},
        status.HTTP_404_NOT_FOUND: {"description": "Session inconnue ou d'une autre boutique"},
        status.HTTP_409_CONFLICT: {"description": "CASH_SESSION_CLOSED ou IDEMPOTENCY_CONFLICT"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "VALIDATION_ERROR ou INSUFFICIENT_CASH"
        },
    },
    summary="Entrée ou sortie d'espèces",
)
async def record_cash_movement(
    session_id: UUID,
    payload: CashMovementCreate,
    response: Response,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> CashMovementResponse:
    """Enregistre un mouvement. **201** : créé ; **200** : retry du même `id`."""
    movement, created = await CashSessionService(db).record_movement(
        store_id, user_id, session_id, payload
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return CashMovementResponse.model_validate(movement)


@router.post(
    "/{session_id}/close",
    response_model=CashSessionDetailResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Session inconnue ou d'une autre boutique"},
        status.HTTP_409_CONFLICT: {
            "description": "CASH_SESSION_CLOSED : session déjà clôturée avec d'autres valeurs"
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "VALIDATION_ERROR (note manquante sur écart, closed_at invalide…)"
        },
    },
    summary="Clôturer une session de caisse",
)
async def close_cash_session(
    session_id: UUID,
    payload: CashSessionClose,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> CashSessionDetailResponse:
    """Clôture atomique : solde recalculé par le serveur, écart, note si écart.

    **200** aussi pour un retry (mêmes `counted_amount` et `closed_at`).
    """
    return await CashSessionService(db).close(store_id, user_id, session_id, payload)
