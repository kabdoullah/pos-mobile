"""Tests de la configuration du backoffice admin (variable et validation du secret)."""

from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from app.core import seed
from app.core.config import Settings, settings

_JWT = "j" * 40


def _settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key in ("ADMIN_JWT_SECRET", "ADMIN_JWT_SECRET_KEY", "ENVIRONMENT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", _JWT)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_admin_jwt_secret_canonical_name(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, ADMIN_JWT_SECRET="x" * 40)
    assert s.admin_jwt_secret_key.get_secret_value() == "x" * 40


def test_admin_jwt_secret_legacy_name(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, ADMIN_JWT_SECRET_KEY="y" * 40)
    assert s.admin_jwt_secret_key.get_secret_value() == "y" * 40


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_admin_secret_too_short_rejected(monkeypatch: pytest.MonkeyPatch, environment: str) -> None:
    with pytest.raises(ValidationError):
        _settings(monkeypatch, ENVIRONMENT=environment, ADMIN_JWT_SECRET="short")


def test_admin_secret_equal_to_jwt_secret_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        _settings(monkeypatch, ENVIRONMENT="production", ADMIN_JWT_SECRET=_JWT)


def test_admin_secret_valid_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, ENVIRONMENT="production", ADMIN_JWT_SECRET="k" * 32)
    assert s.admin_jwt_secret_key.get_secret_value() == "k" * 32


def test_admin_secret_empty_allowed_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, ENVIRONMENT="production")
    assert s.admin_jwt_secret_key.get_secret_value() == ""


def test_short_admin_secret_allowed_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, ENVIRONMENT="local", ADMIN_JWT_SECRET="short")
    assert s.admin_jwt_secret_key.get_secret_value() == "short"


async def test_support_contact_missing_warning() -> None:
    with (
        patch.object(settings, "admin_jwt_secret_key", SecretStr("a" * 48)),
        patch.object(settings, "support_contact", ""),
        patch.object(settings, "admin_email", ""),
        patch.object(seed, "logger") as log,
    ):
        await seed.seed_platform_admin()
    log.warning.assert_called_once_with("support_contact_missing")
