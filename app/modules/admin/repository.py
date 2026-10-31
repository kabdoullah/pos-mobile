"""Accès données du module admin."""

from decimal import Decimal
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import PlatformAdmin


class PlatformMetricsRow(TypedDict):
    """Ligne d'indicateurs plateforme (montants en Decimal, comptes en int)."""

    stores_total: int
    stores_new_7d: int
    stores_suspended: int
    stores_active_7d: int
    stores_inactive_14d: int
    sales_today_count: int
    sales_today_amount: Decimal
    sales_7d_count: int
    sales_7d_amount: Decimal


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
        le compte pour ``lock_minutes`` minutes. Un verrou encore actif n'est
        jamais modifié (ni compteur, ni échéance : pas de prolongation).
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
                WHERE id = :id AND (locked_until IS NULL OR locked_until <= now())
                """
            ),
            {"id": admin_id, "max_failures": max_failures, "lock_minutes": lock_minutes},
        )

    async def register_successful_login(self, admin_id: UUID) -> None:
        """Remet à zéro compteur et verrou, horodate la connexion (un seul UPDATE)."""
        await self.db.execute(
            text(
                "UPDATE platform_admins SET failed_login_count = 0, locked_until = NULL, "
                "last_login_at = now() WHERE id = :id"
            ),
            {"id": admin_id},
        )

    async def round_trip(self) -> None:
        """Aller-retour DB factice (aligne le temps de réponse d'un email inconnu)."""
        await self.db.execute(text("SELECT 1"))

    async def platform_metrics(self) -> PlatformMetricsRow:
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
                SELECT stores_total, stores_new_7d, stores_suspended, stores_active_7d,
                       stores_inactive_14d, sales_today_count, sales_today_amount,
                       sales_7d_count, sales_7d_amount
                FROM store_stats, sale_stats
                """
            )
        )
        return cast("PlatformMetricsRow", dict(result.mappings().one()))

    async def list_stores(
        self,
        *,
        search: str | None,
        status: Literal["all", "active", "suspended"],
        inactive: bool,
        sort: Literal["last_sale", "created"],
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Liste paginée des boutiques (SQL paramétré ; nécessite le flag RLS admin)."""
        conditions = ["TRUE"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params["pattern"] = f"%{escaped}%"
            conditions.append(
                "(s.name ILIKE :pattern ESCAPE '\\' OR u.phone_number ILIKE :pattern ESCAPE '\\')"
            )
        if status == "active":
            conditions.append("s.suspended_at IS NULL")
        elif status == "suspended":
            conditions.append("s.suspended_at IS NOT NULL")
        if inactive:
            conditions.append(
                "(s.suspended_at IS NULL AND s.created_at < now() - interval '14 days' "
                "AND (st.last_sale_at IS NULL OR st.last_sale_at < now() - interval '14 days'))"
            )
        order_by = (
            "st.last_sale_at DESC NULLS LAST, s.created_at DESC"
            if sort == "last_sale"
            else "s.created_at DESC"
        )
        where = " AND ".join(conditions)
        stores_from = "FROM stores s JOIN users u ON u.id = s.owner_id"
        sales_join = (
            "LEFT JOIN LATERAL (SELECT max(created_at) AS last_sale_at, count(*) AS sales_count "
            "FROM sales WHERE store_id = s.id) st ON TRUE"
        )
        # Le count ne paie l'agrégat des ventes que si le filtre inactive l'utilise.
        count_from = f"{stores_from} {sales_join if inactive else ''}"
        total = (
            await self.db.execute(
                text(f"SELECT count(*) {count_from} WHERE {where}"),
                params,
            )
        ).scalar_one()
        rows = await self.db.execute(
            text(
                f"""
                SELECT s.id, s.name, u.phone_number AS owner_phone, s.created_at,
                       st.last_sale_at, COALESCE(st.sales_count, 0) AS sales_count,
                       s.suspended_at, s.suspension_reason
                {stores_from} {sales_join}
                WHERE {where}
                ORDER BY {order_by}, s.id LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        return [dict(r) for r in rows.mappings()], int(total)

    async def get_store_item(self, store_id: UUID) -> dict[str, Any] | None:
        """Une boutique au format de la liste, ou None."""
        rows = await self.db.execute(
            text(
                """
                SELECT s.id, s.name, u.phone_number AS owner_phone, s.created_at,
                       st.last_sale_at, COALESCE(st.sales_count, 0) AS sales_count,
                       s.suspended_at, s.suspension_reason
                FROM stores s
                JOIN users u ON u.id = s.owner_id
                LEFT JOIN (
                    SELECT store_id, max(created_at) AS last_sale_at, count(*) AS sales_count
                    FROM sales WHERE store_id = :sid GROUP BY store_id
                ) st ON st.store_id = s.id
                WHERE s.id = :sid
                """
            ),
            {"sid": store_id},
        )
        row = rows.mappings().first()
        return dict(row) if row else None
