"""Routes du backoffice admin."""

from fastapi import APIRouter, status

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
