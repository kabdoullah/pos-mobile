"""Schémas Pydantic du module admin."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AdminLoginRequest(BaseModel):
    """Identifiants de connexion admin."""

    email: EmailStr
    password: str


class AdminTokenResponse(BaseModel):
    """Token d'accès admin."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int


class PlatformMetrics(BaseModel):
    """Indicateurs globaux de la plateforme (montants en FCFA, chaînes décimales)."""

    stores_total: int
    stores_new_7d: int
    stores_active_7d: int
    stores_inactive_14d: int
    stores_suspended: int
    stores_email_verified: int
    users_without_store: int
    sales_today_count: int
    sales_today_amount: str
    sales_7d_count: int
    sales_7d_amount: str


class AdminStoreItem(BaseModel):
    """Boutique vue par le backoffice."""

    id: UUID
    name: str
    owner_phone: str
    owner_email: str | None
    owner_email_verified: bool
    created_at: datetime
    last_sale_at: datetime | None
    sales_count: int
    suspended_at: datetime | None
    suspension_reason: str | None


class AdminStorePage(BaseModel):
    """Page de boutiques."""

    items: list[AdminStoreItem]
    total: int


class SuspendRequest(BaseModel):
    """Corps de la suspension d'une boutique."""

    reason: str | None = Field(default=None, max_length=500)


AuditAction = Literal["login", "store_suspended", "store_reactivated"]


class AuditEntry(BaseModel):
    """Entrée du journal des actions admin."""

    id: UUID
    created_at: datetime
    action: AuditAction
    admin_email: str
    store_id: UUID | None
    store_name: str | None
    reason: str | None


class AuditPage(BaseModel):
    """Page du journal."""

    items: list[AuditEntry]
    total: int


class AdminStoreDetail(AdminStoreItem):
    """Fiche boutique : activité agrégée, propriétaire et historique admin."""

    address: str | None
    phone: str | None
    ncc: str | None
    vat_subject: bool
    owner_display_name: str | None
    owner_created_at: datetime
    owner_is_active: bool
    products_count: int
    sales_30d_count: int
    sales_30d_amount: str
    history: list[AuditEntry]


class DailyPoint(BaseModel):
    """Activité de la plateforme sur un jour (Africa/Abidjan)."""

    day: date
    new_users: int
    new_stores: int
    active_stores: int
    sales_count: int
    sales_amount: str


class AdminUserItem(BaseModel):
    """Compte commerçant vu par le backoffice."""

    id: UUID
    phone_number: str
    display_name: str | None
    email: str | None
    email_verified: bool
    is_active: bool
    created_at: datetime
    store_id: UUID | None
    store_name: str | None


class AdminUserPage(BaseModel):
    """Page de comptes."""

    items: list[AdminUserItem]
    total: int
