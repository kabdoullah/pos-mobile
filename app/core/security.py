"""Helpers de sécurité : hash des mots de passe et gestion JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2 (via pwdlib)."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie qu'un mot de passe correspond au hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(user_id: UUID, store_id: UUID | None = None) -> str:
    """Génère un JWT access token (durée courte, ~1h)."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
    }
    if store_id is not None:
        payload["store_id"] = str(store_id)
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(user_id: UUID) -> str:
    """Génère un JWT refresh token (durée longue, ~30j)."""
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any] | None:
    """Décode un JWT. Retourne None si invalide ou expiré."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None


ADMIN_TOKEN_AUDIENCE = "pos-admin"  # noqa: S105


def create_admin_token(admin_id: UUID) -> str:
    """Génère un JWT admin (clé et audience distinctes des tokens commerçants)."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.admin_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(admin_id),
        "exp": expire,
        "type": "admin",
        "aud": ADMIN_TOKEN_AUDIENCE,
    }
    return jwt.encode(
        payload,
        settings.admin_jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_admin_token(token: str) -> dict[str, Any] | None:
    """Décode un JWT admin. None si clé vide, token invalide, expiré ou mauvais type."""
    secret = settings.admin_jwt_secret_key.get_secret_value()
    if not secret:
        return None
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            audience=ADMIN_TOKEN_AUDIENCE,
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "admin":
        return None
    return payload
