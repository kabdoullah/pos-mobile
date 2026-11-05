"""Accès données du module admin."""

from decimal import Decimal
from typing import Any, Literal, TypedDict, cast
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import AdminAuditLogEntry, PlatformAdmin


def _like_pattern(search: str) -> str:
    """Motif ILIKE « contient », jokers échappés (à utiliser avec ESCAPE '\\')."""
    escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class PlatformMetricsRow(TypedDict):
    """Ligne d'indicateurs plateforme (montants en Decimal, comptes en int)."""

    stores_total: int
    stores_new_7d: int
    stores_suspended: int
    stores_active_7d: int
    stores_inactive_14d: int
    stores_email_verified: int
    users_without_store: int
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
                            )) AS stores_inactive_14d,
                        count(*) FILTER (
                            WHERE EXISTS (
                                SELECT 1 FROM users u WHERE u.id = stores.owner_id
                                AND u.email_verified_at IS NOT NULL
                            )) AS stores_email_verified
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
                ), user_stats AS (
                    SELECT count(*) AS users_without_store
                    FROM users u
                    WHERE NOT EXISTS (SELECT 1 FROM stores s WHERE s.owner_id = u.id)
                )
                SELECT stores_total, stores_new_7d, stores_suspended, stores_active_7d,
                       stores_inactive_14d, stores_email_verified, users_without_store,
                       sales_today_count, sales_today_amount,
                       sales_7d_count, sales_7d_amount
                FROM store_stats, sale_stats, user_stats
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
            params["pattern"] = _like_pattern(search)
            conditions.append(
                "(s.name ILIKE :pattern ESCAPE '\\' OR u.phone_number ILIKE :pattern ESCAPE '\\' "
                "OR u.email ILIKE :pattern ESCAPE '\\')"
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
                SELECT s.id, s.name, u.phone_number AS owner_phone, u.email AS owner_email,
                       u.email_verified_at IS NOT NULL AS owner_email_verified,
                       s.created_at,
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
                SELECT s.id, s.name, u.phone_number AS owner_phone, u.email AS owner_email,
                       u.email_verified_at IS NOT NULL AS owner_email_verified,
                       s.created_at,
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

    async def get_store_detail(self, store_id: UUID) -> dict[str, Any] | None:
        """Fiche boutique : champs de la liste + profil, propriétaire et activité 30 j."""
        rows = await self.db.execute(
            text(
                """
                SELECT s.id, s.name, u.phone_number AS owner_phone, u.email AS owner_email,
                       u.email_verified_at IS NOT NULL AS owner_email_verified,
                       s.created_at, s.suspended_at, s.suspension_reason,
                       s.address, s.phone, s.ncc, s.vat_subject,
                       u.display_name AS owner_display_name, u.created_at AS owner_created_at,
                       u.is_active AS owner_is_active,
                       (SELECT count(*) FROM products p
                        WHERE p.store_id = s.id AND p.deleted_at IS NULL) AS products_count,
                       st.last_sale_at, COALESCE(st.sales_count, 0) AS sales_count,
                       COALESCE(st.sales_30d_count, 0) AS sales_30d_count,
                       COALESCE(st.sales_30d_amount, 0) AS sales_30d_amount
                FROM stores s
                JOIN users u ON u.id = s.owner_id
                LEFT JOIN (
                    SELECT store_id, max(created_at) AS last_sale_at, count(*) AS sales_count,
                           count(*) FILTER (
                               WHERE created_at >= now() - interval '30 days') AS sales_30d_count,
                           SUM(total_amount) FILTER (
                               WHERE created_at >= now() - interval '30 days') AS sales_30d_amount
                    FROM sales WHERE store_id = :sid GROUP BY store_id
                ) st ON st.store_id = s.id
                WHERE s.id = :sid
                """
            ),
            {"sid": store_id},
        )
        row = rows.mappings().first()
        return dict(row) if row else None

    async def daily_metrics(self, days: int) -> list[dict[str, Any]]:
        """Activité jour par jour (Africa/Abidjan) sur ``days`` jours, jours vides à 0."""
        rows = await self.db.execute(
            text(
                """
                WITH bounds AS (
                    SELECT (now() AT TIME ZONE 'Africa/Abidjan')::date AS today,
                           (now() AT TIME ZONE 'Africa/Abidjan')::date
                               - (CAST(:days AS integer) - 1) AS first_day
                ), since AS (
                    SELECT first_day, first_day::timestamp AT TIME ZONE 'Africa/Abidjan' AS ts
                    FROM bounds
                ), days AS (
                    SELECT generate_series(first_day, today, interval '1 day')::date AS day
                    FROM bounds
                ), u AS (
                    SELECT (created_at AT TIME ZONE 'Africa/Abidjan')::date AS day, count(*) AS n
                    FROM users WHERE created_at >= (SELECT ts FROM since) GROUP BY 1
                ), st AS (
                    SELECT (created_at AT TIME ZONE 'Africa/Abidjan')::date AS day, count(*) AS n
                    FROM stores WHERE created_at >= (SELECT ts FROM since) GROUP BY 1
                ), sa AS (
                    SELECT (created_at AT TIME ZONE 'Africa/Abidjan')::date AS day,
                           count(DISTINCT store_id) AS active_stores, count(*) AS sales_count,
                           SUM(total_amount) AS sales_amount
                    FROM sales WHERE created_at >= (SELECT ts FROM since) GROUP BY 1
                )
                SELECT d.day, COALESCE(u.n, 0) AS new_users, COALESCE(st.n, 0) AS new_stores,
                       COALESCE(sa.active_stores, 0) AS active_stores,
                       COALESCE(sa.sales_count, 0) AS sales_count,
                       COALESCE(sa.sales_amount, 0) AS sales_amount
                FROM days d
                LEFT JOIN u ON u.day = d.day
                LEFT JOIN st ON st.day = d.day
                LEFT JOIN sa ON sa.day = d.day
                ORDER BY d.day
                """
            ),
            {"days": days},
        )
        return [dict(r) for r in rows.mappings()]

    async def list_users(
        self,
        *,
        search: str | None,
        store: Literal["all", "with", "without"],
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Comptes commerçants paginés, avec leur boutique éventuelle (flag RLS admin requis)."""
        conditions = ["TRUE"]
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if search:
            params["pattern"] = _like_pattern(search)
            conditions.append(
                "(u.phone_number ILIKE :pattern ESCAPE '\\' OR u.email ILIKE :pattern ESCAPE '\\' "
                "OR u.display_name ILIKE :pattern ESCAPE '\\')"
            )
        if store == "with":
            conditions.append("s.id IS NOT NULL")
        elif store == "without":
            conditions.append("s.id IS NULL")
        where = " AND ".join(conditions)
        source = "FROM users u LEFT JOIN stores s ON s.owner_id = u.id"
        total = (
            await self.db.execute(text(f"SELECT count(*) {source} WHERE {where}"), params)
        ).scalar_one()
        rows = await self.db.execute(
            text(
                f"""
                SELECT u.id, u.phone_number, u.display_name, u.email,
                       u.email_verified_at IS NOT NULL AS email_verified, u.is_active,
                       u.created_at, s.id AS store_id, s.name AS store_name
                {source}
                WHERE {where}
                ORDER BY u.created_at DESC, u.id LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        return [dict(r) for r in rows.mappings()], int(total)

    async def add_audit_entry(
        self,
        *,
        admin_id: UUID,
        admin_email: str,
        action: str,
        store_id: UUID | None = None,
        store_name: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Ajoute une entrée au journal (dans la transaction courante)."""
        self.db.add(
            AdminAuditLogEntry(
                admin_id=admin_id,
                admin_email=admin_email,
                action=action,
                store_id=store_id,
                store_name=store_name,
                reason=reason,
            )
        )
        await self.db.flush()

    async def list_audit(
        self, *, store_id: UUID | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Journal paginé, du plus récent au plus ancien, filtrable par boutique."""
        log = AdminAuditLogEntry
        stmt = select(
            log.id,
            log.created_at,
            log.action,
            log.admin_email,
            log.store_id,
            log.store_name,
            log.reason,
        )
        count_stmt = select(func.count()).select_from(log)
        if store_id is not None:
            stmt = stmt.where(log.store_id == store_id)
            count_stmt = count_stmt.where(log.store_id == store_id)
        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = await self.db.execute(
            stmt.order_by(log.created_at.desc(), log.id).limit(limit).offset(offset)
        )
        return [dict(r) for r in rows.mappings()], int(total)
