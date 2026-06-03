"""Configuration centralisée chargée depuis les variables d'environnement."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings de l'application, chargées depuis .env et l'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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
