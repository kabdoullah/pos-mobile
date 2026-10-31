"""Dépendances FastAPI du module admin."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import DbSession
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_admin_token
from app.modules.admin.repository import AdminRepository


async def get_current_admin_id(request: Request, db: DbSession) -> UUID:
    """Valide le Bearer admin et vérifie que l'admin existe toujours."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise UnauthorizedError("Admin authentication required")
    payload = decode_admin_token(auth_header.split(" ", 1)[1])
    try:
        admin_id = UUID(str(payload["sub"])) if payload else None
    except (KeyError, ValueError):
        admin_id = None
    if admin_id is None or await AdminRepository(db).get_by_id(admin_id) is None:
        raise UnauthorizedError("Admin authentication required")
    return admin_id


CurrentAdminId = Annotated[UUID, Depends(get_current_admin_id)]


async def get_admin_db(db: DbSession, _admin: CurrentAdminId) -> AsyncSession:
    """Session DB avec le flag RLS plateforme (lecture cross-tenant, transaction courante)."""
    await db.execute(text("SET LOCAL app.is_platform_admin = 'on'"))
    return db


AdminDbSession = Annotated[AsyncSession, Depends(get_admin_db)]
