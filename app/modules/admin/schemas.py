"""Schémas Pydantic du module admin."""

from datetime import datetime
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
    sales_today_count: int
    sales_today_amount: str
    sales_7d_count: int
    sales_7d_amount: str


class AdminStoreItem(BaseModel):
    """Boutique vue par le backoffice."""

    id: UUID
    name: str
    owner_phone: str
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
