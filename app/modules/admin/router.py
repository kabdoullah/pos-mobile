"""Routes du backoffice admin."""

from typing import Any

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.modules.admin import schemas
from app.modules.admin.dependencies import CurrentAdminId
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
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Métriques plateforme",
)
async def get_metrics(_admin_id: CurrentAdminId) -> dict[str, Any]:
    """Placeholder protégé (complété dans une tâche ultérieure)."""
    return {}
