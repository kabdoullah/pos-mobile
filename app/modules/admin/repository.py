"""Accès données du module admin."""

from uuid import UUID

from sqlalchemy import select, text
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

    async def register_failed_login(
        self, admin_id: UUID, max_failures: int, lock_minutes: int
    ) -> None:
        """Incrémente atomiquement le compteur d'échecs (une seule requête SQL).

        Si un verrou a expiré, le compteur repart de 1. Au seuil, verrouille
        le compte pour ``lock_minutes`` minutes.
        """
        await self.db.execute(
            text(
                """
                UPDATE platform_admins SET
                    failed_login_count = CASE
                        WHEN locked_until IS NOT NULL AND locked_until <= now() THEN 1
                        ELSE failed_login_count + 1 END,
                    locked_until = CASE
                        WHEN (CASE WHEN locked_until IS NOT NULL AND locked_until <= now()
                                   THEN 1 ELSE failed_login_count + 1 END) >= :max_failures
                            THEN now() + make_interval(mins => :lock_minutes)
                        WHEN locked_until IS NOT NULL AND locked_until <= now() THEN NULL
                        ELSE locked_until END
                WHERE id = :id
                """
            ),
            {"id": admin_id, "max_failures": max_failures, "lock_minutes": lock_minutes},
        )
