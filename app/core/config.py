"""Configuration centralisée chargée depuis les variables d'environnement."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MIN_ADMIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Settings de l'application, chargées depuis .env et l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Application
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"

    # Database
    database_url: str = Field(..., description="URL PostgreSQL avec asyncpg")
    database_pool_size: int = 10
    database_max_overflow: int = 5

    # Auth
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # Email (Resend HTTP API — port 443, marche derrière hébergeurs bloquant SMTP)
    email_enabled: bool = True
    resend_api_key: SecretStr = SecretStr("")
    mail_from_email: str = "onboarding@resend.dev"  # domaine vérifié Resend en prod
    mail_from_name: str = "POS Mobile CI"

    # Frontend
    app_frontend_url: str = "http://localhost:3000"

    # Rate limiting
    redis_url: str = ""

    # CORS
    cors_origins: str = ""

    # Super admin seed (optionnel — laissez vide pour ne pas créer de compte au démarrage)
    superadmin_phone: str = ""
    superadmin_password: SecretStr = SecretStr("")
    superadmin_email: str = ""

    # Backoffice admin plateforme (clé JWT distincte de celle des commerçants ;
    # vide = accès admin désactivé)
    admin_jwt_secret_key: SecretStr = Field(
        SecretStr(""),
        validation_alias=AliasChoices("ADMIN_JWT_SECRET", "ADMIN_JWT_SECRET_KEY"),
    )
    admin_token_expire_minutes: int = 120
    admin_email: str = ""
    admin_password: SecretStr = SecretStr("")
    support_contact: str = ""
    # Numéro WhatsApp du support (indicatif pays inclus, ex. +225…), optionnel.
    support_whatsapp: str = ""

    @model_validator(mode="after")
    def _check_admin_secret(self) -> "Settings":
        """Impose un secret admin robuste et distinct en staging/production."""
        secret = self.admin_jwt_secret_key.get_secret_value()
        if self.environment in ("staging", "production") and secret:
            if len(secret) < _MIN_ADMIN_SECRET_LENGTH:
                raise ValueError("ADMIN_JWT_SECRET doit faire au moins 32 caractères")
            if secret == self.jwt_secret_key.get_secret_value():
                raise ValueError("ADMIN_JWT_SECRET doit différer de JWT_SECRET_KEY")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Convertit la string CSV en liste."""
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance de Settings (cached)."""
    return Settings()


settings = get_settings()
