"""Routes du module stores."""

from fastapi import APIRouter, status

from app.core.db import DbSession, TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.modules.stores import schemas
from app.modules.stores.service import StoreService

router = APIRouter()


@router.post(
    "",
    response_model=schemas.StoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer une boutique",
)
async def create_store(
    payload: schemas.StoreCreate,
    db: DbSession,
    user_id: CurrentUserId,
) -> schemas.StoreResponse:
    """Crée une boutique pour l'utilisateur courant. 409 si une boutique existe déjà."""
    store = await StoreService(db).create_for_user(user_id, payload)
    return schemas.StoreResponse.model_validate(store)


@router.get(
    "/me",
    response_model=schemas.StoreResponse,
    summary="Ma boutique",
)
async def get_my_store(
    db: TenantDbSession,
    user_id: CurrentUserId,
    _store_id: CurrentStoreId,
) -> schemas.StoreResponse:
    """Retourne la boutique de l'utilisateur courant."""
    store = await StoreService(db).get_for_user(user_id)
    return schemas.StoreResponse.model_validate(store)


@router.patch(
    "/me",
    response_model=schemas.StoreResponse,
    summary="Mettre à jour ma boutique",
)
async def update_my_store(
    payload: schemas.StoreUpdate,
    db: TenantDbSession,
    user_id: CurrentUserId,
    _store_id: CurrentStoreId,
) -> schemas.StoreResponse:
    """Met à jour les champs fournis de la boutique (PATCH partiel)."""
    store = await StoreService(db).update_for_user(user_id, payload)
    return schemas.StoreResponse.model_validate(store)
