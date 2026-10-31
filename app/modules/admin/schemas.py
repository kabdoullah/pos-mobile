"""Schémas Pydantic du module admin."""

from typing import Literal

from pydantic import BaseModel, EmailStr


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
