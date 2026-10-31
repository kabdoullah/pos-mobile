"""Routes du backoffice admin."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.db import DbSession
from app.modules.admin import schemas
from app.modules.admin.dependencies import AdminDbSession
from app.modules.admin.service import AdminService

router = APIRouter()


@router.post(
    "/auth/login",
    response_model=schemas.AdminTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Connexion administrateur plateforme",
)
async def admin_login(
    payload: schemas.AdminLoginRequest, db: DbSession
) -> schemas.AdminTokenResponse:
    """Authentifie un administrateur plateforme."""
    return await AdminService(db).login(payload)


@router.get(
    "/metrics",
    response_model=schemas.PlatformMetrics,
    status_code=status.HTTP_200_OK,
    summary="Indicateurs plateforme",
)
async def get_metrics(db: AdminDbSession) -> schemas.PlatformMetrics:
    """Indicateurs globaux (boutiques, ventes) toutes boutiques confondues."""
    return await AdminService(db).get_platform_metrics()


@router.get(
    "/stores",
    response_model=schemas.AdminStorePage,
    status_code=status.HTTP_200_OK,
    summary="Liste des boutiques",
)
async def list_stores(
    db: AdminDbSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    store_status: Annotated[Literal["all", "active", "suspended"], Query(alias="status")] = "all",
    inactive: bool = False,
    sort: Literal["last_sale", "created"] = "last_sale",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.AdminStorePage:
    """Boutiques toutes confondues, avec recherche, filtres et pagination."""
    return await AdminService(db).list_stores(
        search=search,
        status=store_status,
        inactive=inactive,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/stores/{store_id}/suspend",
    response_model=schemas.AdminStoreItem,
    status_code=status.HTTP_200_OK,
    summary="Suspendre une boutique",
)
async def suspend_store(
    store_id: UUID, payload: schemas.SuspendRequest, db: AdminDbSession
) -> schemas.AdminStoreItem:
    """Suspend la boutique (le commerçant est bloqué au prochain contact serveur)."""
    return await AdminService(db).set_store_suspension(store_id, True, payload.reason)


@router.post(
    "/stores/{store_id}/reactivate",
    response_model=schemas.AdminStoreItem,
    status_code=status.HTTP_200_OK,
    summary="Réactiver une boutique",
)
async def reactivate_store(store_id: UUID, db: AdminDbSession) -> schemas.AdminStoreItem:
    """Lève la suspension de la boutique."""
    return await AdminService(db).set_store_suspension(store_id, False)
