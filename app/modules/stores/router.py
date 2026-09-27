"""Routes du module stores."""

from typing import Annotated

from fastapi import APIRouter, Header, Response, UploadFile, status

from app.core.db import DbSession, TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.core.images import MAX_UPLOAD_BYTES, image_response
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


# ---------------------------------------------------------------------------
# Logo — ADR-0008 (en ligne uniquement)
# ---------------------------------------------------------------------------


@router.put(
    "/me/logo",
    response_model=schemas.StoreResponse,
    summary="Définir le logo de ma boutique",
)
async def upload_my_logo(
    file: UploadFile,
    db: TenantDbSession,
    user_id: CurrentUserId,
    _store_id: CurrentStoreId,
) -> schemas.StoreResponse:
    """Remplace le logo (JPEG, PNG ou WebP, 5 Mo max), ré-encodé en WebP 384 px.

    Retourne la boutique avec son nouveau `logo_version`. 413 / 422 si refusé.
    """
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    store = await StoreService(db).set_logo_for_user(user_id, raw)
    return schemas.StoreResponse.model_validate(store)


@router.get(
    "/me/logo",
    response_class=Response,
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_304_NOT_MODIFIED: {"description": "Version déjà en cache (If-None-Match)"},
        status.HTTP_404_NOT_FOUND: {"description": "Pas de logo"},
    },
    summary="Logo de ma boutique",
)
async def get_my_logo(
    db: TenantDbSession,
    user_id: CurrentUserId,
    _store_id: CurrentStoreId,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """Logo WebP, avec ETag (SHA-256) et cache long côté client."""
    logo = await StoreService(db).get_logo_for_user(user_id)
    return image_response(logo.content, logo.content_type, logo.sha256, if_none_match)


@router.delete(
    "/me/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer le logo de ma boutique",
)
async def delete_my_logo(
    db: TenantDbSession,
    user_id: CurrentUserId,
    _store_id: CurrentStoreId,
) -> None:
    """Supprime le logo (`logo_version` repasse à null)."""
    await StoreService(db).delete_logo_for_user(user_id)
