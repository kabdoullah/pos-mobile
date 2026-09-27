"""Schémas Pydantic du module auth."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.validators import validate_e164


class RegisterRequest(BaseModel):
    """Payload d'inscription."""

    phone_number: str = Field(..., min_length=8, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    email: EmailStr | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_e164(cls, v: str) -> str:
        return validate_e164(v)


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


class UserMeResponse(BaseModel):
    """Profil de l'utilisateur connecté."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone_number: str
    email: str | None
    display_name: str | None = None


class UserMeUpdate(BaseModel):
    """Mise à jour du profil. `display_name` vide ou null = retiré du reçu."""

    display_name: str | None = Field(None, max_length=80)

    @field_validator("display_name", mode="before")
    @classmethod
    def blank_to_none(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v
