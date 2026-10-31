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
