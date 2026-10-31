"""Accès données du module admin."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import PlatformAdmin


class AdminRepository:
    """Requêtes sur les administrateurs plateforme."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, admin_id: UUID) -> PlatformAdmin | None:
        """Retourne l'admin par id."""
        result = await self.db.execute(select(PlatformAdmin).where(PlatformAdmin.id == admin_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> PlatformAdmin | None:
        """Retourne l'admin par email (déjà normalisé en minuscules)."""
        result = await self.db.execute(select(PlatformAdmin).where(PlatformAdmin.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, password_hash: str) -> PlatformAdmin:
        """Crée un admin."""
        admin = PlatformAdmin(email=email, password_hash=password_hash)
        self.db.add(admin)
        await self.db.flush()
        return admin
