"""Schémas Pydantic du module auth."""

import re
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


class RegisterRequest(BaseModel):
    """Payload d'inscription."""

    phone_number: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    email: EmailStr | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_e164(cls, v: str) -> str:
        if not _E164_RE.match(v):
            raise ValueError("Phone number must be in E.164 format (e.g. +2250700000000).")
        return v


class RegisterResponse(BaseModel):
    """Réponse après inscription réussie."""

    user_id: UUID
    phone_number: str
    message: str


class LoginRequest(BaseModel):
    """Payload de connexion."""

    phone_number: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Payload de renouvellement de token."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Réponse contenant les JWT access et refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int  # durée de vie de l'access_token en secondes


class ForgotPasswordRequest(BaseModel):
    """Demande d'email de réinitialisation."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Confirmation de réinitialisation avec nouveau mot de passe."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
