"""Routes du backoffice admin."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from app.core.db import DbSession
from app.modules.admin import schemas
from app.modules.admin.dependencies import AdminDbSession, CurrentAdminId
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
    "/metrics/daily",
    response_model=list[schemas.DailyPoint],
    status_code=status.HTTP_200_OK,
    summary="Activité quotidienne de la plateforme",
)
async def get_daily_metrics(
    db: AdminDbSession, days: Annotated[int, Query(ge=7, le=90)] = 30
) -> list[schemas.DailyPoint]:
    """Nouveaux comptes, nouvelles boutiques, boutiques actives et ventes par jour."""
    return await AdminService(db).get_daily_metrics(days)


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


@router.get(
    "/stores/{store_id}",
    response_model=schemas.AdminStoreDetail,
    status_code=status.HTTP_200_OK,
    summary="Fiche d'une boutique",
)
async def get_store(store_id: UUID, db: AdminDbSession) -> schemas.AdminStoreDetail:
    """Profil, propriétaire, activité sur 30 jours et historique admin de la boutique."""
    return await AdminService(db).get_store_detail(store_id)


@router.post(
    "/stores/{store_id}/suspend",
    response_model=schemas.AdminStoreItem,
    status_code=status.HTTP_200_OK,
    summary="Suspendre une boutique",
)
async def suspend_store(
    store_id: UUID,
    payload: schemas.SuspendRequest,
    db: AdminDbSession,
    admin_id: CurrentAdminId,
) -> schemas.AdminStoreItem:
    """Suspend la boutique (le commerçant est bloqué au prochain contact serveur)."""
    return await AdminService(db).set_store_suspension(store_id, True, admin_id, payload.reason)


@router.post(
    "/stores/{store_id}/reactivate",
    response_model=schemas.AdminStoreItem,
    status_code=status.HTTP_200_OK,
    summary="Réactiver une boutique",
)
async def reactivate_store(
    store_id: UUID, db: AdminDbSession, admin_id: CurrentAdminId
) -> schemas.AdminStoreItem:
    """Lève la suspension de la boutique."""
    return await AdminService(db).set_store_suspension(store_id, False, admin_id)


@router.get(
    "/users",
    response_model=schemas.AdminUserPage,
    status_code=status.HTTP_200_OK,
    summary="Liste des comptes commerçants",
)
async def list_users(
    db: AdminDbSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    store: Literal["all", "with", "without"] = "all",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.AdminUserPage:
    """Comptes commerçants, filtrables selon qu'ils ont créé leur boutique ou non."""
    return await AdminService(db).list_users(search=search, store=store, limit=limit, offset=offset)


@router.post(
    "/users/{user_id}/password-reset-link",
    response_model=schemas.PasswordResetLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Générer un lien de réinitialisation du mot de passe",
)
async def issue_password_reset_link(
    user_id: UUID,
    payload: schemas.PasswordResetLinkRequest,
    response: Response,
    db: AdminDbSession,
    admin_id: CurrentAdminId,
) -> schemas.PasswordResetLinkResponse:
    """Lien 1h à usage unique, à transmettre au numéro du compte (ADR-0014)."""
    response.headers["Cache-Control"] = "no-store"
    return await AdminService(db).issue_password_reset_link(user_id, admin_id, payload.reason)


@router.get(
    "/audit-log",
    response_model=schemas.AuditPage,
    status_code=status.HTTP_200_OK,
    summary="Journal des actions admin",
)
async def list_audit_log(
    db: AdminDbSession,
    store_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> schemas.AuditPage:
    """Connexions, suspensions, réactivations et liens de reset, du plus récent au plus ancien."""
    return await AdminService(db).list_audit(store_id=store_id, limit=limit, offset=offset)
