"""Schémas Pydantic du module auth."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload d'inscription."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone_number: str = Field(..., min_length=8, max_length=20)


class RegisterResponse(BaseModel):
    """Réponse après inscription réussie."""

    user_id: UUID
    email: str
    message: str


class LoginRequest(BaseModel):
    """Payload de connexion."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Payload de renouvellement de token."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Réponse contenant les JWT access et refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # durée de vie de l'access_token en secondes


class ForgotPasswordRequest(BaseModel):
    """Demande d'email de réinitialisation."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Confirmation de réinitialisation avec nouveau mot de passe."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
