"""Accès données du module admin."""

from decimal import Decimal
from typing import Any
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

    async def platform_metrics(self) -> dict[str, Any]:
        """Agrège les indicateurs plateforme en SQL (nécessite le flag RLS admin)."""
        result = await self.db.execute(
            text(
                """
                WITH bounds AS (
                    SELECT (date_trunc('day', now() AT TIME ZONE 'Africa/Abidjan')
                            AT TIME ZONE 'Africa/Abidjan') AS today_start
                ), store_stats AS (
                    SELECT
                        count(*) AS stores_total,
                        count(*) FILTER (
                            WHERE created_at >= now() - interval '7 days') AS stores_new_7d,
                        count(*) FILTER (WHERE suspended_at IS NOT NULL) AS stores_suspended,
                        count(*) FILTER (
                            WHERE suspended_at IS NULL AND EXISTS (
                                SELECT 1 FROM sales s WHERE s.store_id = stores.id
                                AND s.created_at >= now() - interval '7 days'
                            )) AS stores_active_7d,
                        count(*) FILTER (
                            WHERE suspended_at IS NULL
                            AND created_at < now() - interval '14 days'
                            AND NOT EXISTS (
                                SELECT 1 FROM sales s WHERE s.store_id = stores.id
                                AND s.created_at >= now() - interval '14 days'
                            )) AS stores_inactive_14d
                    FROM stores
                ), sale_stats AS (
                    SELECT
                        count(*) FILTER (
                            WHERE created_at >= (SELECT today_start FROM bounds)
                        ) AS sales_today_count,
                        COALESCE(SUM(total_amount) FILTER (
                            WHERE created_at >= (SELECT today_start FROM bounds)), 0
                        ) AS sales_today_amount,
                        count(*) FILTER (
                            WHERE created_at >= now() - interval '7 days') AS sales_7d_count,
                        COALESCE(SUM(total_amount) FILTER (
                            WHERE created_at >= now() - interval '7 days'), 0
                        ) AS sales_7d_amount
                    FROM sales
                )
                SELECT * FROM store_stats, sale_stats
                """
            )
        )
        row = dict(result.mappings().one())
        for key in ("sales_today_amount", "sales_7d_amount"):
            row[key] = Decimal(row[key])
        return row
