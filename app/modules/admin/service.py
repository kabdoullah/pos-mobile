"""Logique métier du module admin.

Le service fait ``commit()`` lui-même au login : le compteur d'échecs doit survivre
au rollback de ``get_db`` déclenché par l'exception d'authentification.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import create_admin_token, hash_password, verify_password
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AdminLoginRequest,
    AdminStoreDetail,
    AdminStoreItem,
    AdminStorePage,
    AdminTokenResponse,
    AdminUserItem,
    AdminUserPage,
    AuditEntry,
    AuditPage,
    DailyPoint,
    PlatformMetrics,
)
from app.modules.stores.service import StoreService

MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=15)
_INVALID_CREDENTIALS = "Invalid email or password."
# Hash factice pour garder un temps de réponse constant quand l'email est inconnu.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


class AdminService:
    """Authentification et gestion des administrateurs plateforme."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AdminRepository(db)

    async def login(self, payload: AdminLoginRequest) -> AdminTokenResponse:
        """Authentifie un admin ; verrouille le compte après 5 échecs consécutifs."""
        if not settings.admin_jwt_secret_key.get_secret_value():
            raise ForbiddenError("Admin access is not configured.")

        admin = await self.repo.get_by_email(payload.email.strip().lower())
        if admin is None:
            verify_password(payload.password, _DUMMY_PASSWORD_HASH)
            # Mêmes allers-retours DB que sur mauvais mot de passe (UPDATE + commit).
            await self.repo.round_trip()
            await self.db.commit()
            raise UnauthorizedError(_INVALID_CREDENTIALS)

        now = datetime.now(UTC)
        locked = admin.locked_until is not None and admin.locked_until > now
        password_ok = verify_password(payload.password, admin.password_hash)

        if locked or not password_ok:
            if not locked:
                await self.repo.register_failed_login(
                    admin.id, MAX_FAILED_LOGINS, int(LOCK_DURATION.total_seconds() // 60)
                )
                # Persister le compteur malgré l'exception (get_db fait rollback).
                await self.db.commit()
            raise UnauthorizedError(_INVALID_CREDENTIALS)

        await self.repo.register_successful_login(admin.id)
        await self.repo.add_audit_entry(admin_id=admin.id, admin_email=admin.email, action="login")
        return AdminTokenResponse(
            access_token=create_admin_token(admin.id),
            token_type="bearer",  # noqa: S106
            expires_in=settings.admin_token_expire_minutes * 60,
        )

    async def ensure_seed_admin(self, email: str, password: str) -> bool:
        """Crée l'admin s'il n'existe pas. Ne réécrit jamais un admin existant.

        Retourne True si l'admin a été créé.
        """
        normalized = email.strip().lower()
        if await self.repo.get_by_email(normalized) is not None:
            return False
        await self.repo.create(normalized, hash_password(password))
        return True

    async def get_platform_metrics(self) -> PlatformMetrics:
        """Indicateurs globaux de la plateforme."""
        row = await self.repo.platform_metrics()
        return PlatformMetrics(
            stores_total=row["stores_total"],
            stores_new_7d=row["stores_new_7d"],
            stores_active_7d=row["stores_active_7d"],
            stores_inactive_14d=row["stores_inactive_14d"],
            stores_suspended=row["stores_suspended"],
            stores_email_verified=row["stores_email_verified"],
            users_without_store=row["users_without_store"],
            sales_today_count=row["sales_today_count"],
            sales_today_amount=str(row["sales_today_amount"]),
            sales_7d_count=row["sales_7d_count"],
            sales_7d_amount=str(row["sales_7d_amount"]),
        )

    async def list_stores(
        self,
        *,
        search: str | None,
        status: Literal["all", "active", "suspended"],
        inactive: bool,
        sort: Literal["last_sale", "created"],
        limit: int,
        offset: int,
    ) -> AdminStorePage:
        """Liste paginée et filtrée des boutiques."""
        rows, total = await self.repo.list_stores(
            search=search, status=status, inactive=inactive, sort=sort, limit=limit, offset=offset
        )
        return AdminStorePage(items=[AdminStoreItem(**r) for r in rows], total=total)

    async def set_store_suspension(
        self, store_id: UUID, suspended: bool, admin_id: UUID, reason: str | None = None
    ) -> AdminStoreItem:
        """Suspend ou réactive une boutique (écriture via le module stores) et le journalise."""
        await StoreService(self.db).set_suspension(store_id, suspended, reason)
        row = await self.repo.get_store_item(store_id)
        if row is None:
            raise NotFoundError("Store not found.")
        admin = await self.repo.get_by_id(admin_id)
        if admin is None:
            raise NotFoundError("Admin not found.")
        await self.repo.add_audit_entry(
            admin_id=admin.id,
            admin_email=admin.email,
            action="store_suspended" if suspended else "store_reactivated",
            store_id=store_id,
            store_name=row["name"],
            reason=reason if suspended else None,
        )
        return AdminStoreItem(**row)

    async def get_store_detail(self, store_id: UUID) -> AdminStoreDetail:
        """Fiche boutique avec ses 20 dernières actions admin."""
        row = await self.repo.get_store_detail(store_id)
        if row is None:
            raise NotFoundError("Store not found.")
        history, _ = await self.repo.list_audit(store_id=store_id, limit=20, offset=0)
        return AdminStoreDetail(
            **{**row, "sales_30d_amount": str(row["sales_30d_amount"])},
            history=[AuditEntry(**h) for h in history],
        )

    async def get_daily_metrics(self, days: int) -> list[DailyPoint]:
        """Série quotidienne de l'activité plateforme."""
        rows = await self.repo.daily_metrics(days)
        return [DailyPoint(**{**r, "sales_amount": str(r["sales_amount"])}) for r in rows]

    async def list_users(
        self,
        *,
        search: str | None,
        store: Literal["all", "with", "without"],
        limit: int,
        offset: int,
    ) -> AdminUserPage:
        """Comptes commerçants, avec ou sans boutique."""
        rows, total = await self.repo.list_users(
            search=search, store=store, limit=limit, offset=offset
        )
        return AdminUserPage(items=[AdminUserItem(**r) for r in rows], total=total)

    async def list_audit(self, *, store_id: UUID | None, limit: int, offset: int) -> AuditPage:
        """Journal des actions admin."""
        rows, total = await self.repo.list_audit(store_id=store_id, limit=limit, offset=offset)
        return AuditPage(items=[AuditEntry(**r) for r in rows], total=total)
