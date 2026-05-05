"""Tests du service email et de l'intégration token-email dans AuthService."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailService
from app.core.exceptions import ValidationError
from app.core.security import hash_password, verify_password
from app.modules.auth import schemas
from app.modules.auth.models import EmailVerificationToken, PasswordResetToken, User
from app.modules.auth.repository import PasswordResetTokenRepository, UserRepository
from app.modules.auth.service import AuthService

_PATCH_SEND = "app.core.email.EmailService._send"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("OldPassword1"),
        phone_number="0700000001",
    )
    return await UserRepository(db).create(user)


# ---------------------------------------------------------------------------
# Tests unitaires EmailService (SMTP mocké, pas de DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_verification_email_calls_send() -> None:
    """send_verification_email délègue à _send exactement une fois."""
    service = EmailService()
    with patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send:
        await service.send_verification_email(
            to_email="user@example.com",
            user_name="user@example.com",
            raw_token="abc123token",
        )
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_password_reset_email_calls_send() -> None:
    """send_password_reset_email délègue à _send exactement une fois."""
    service = EmailService()
    with patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send:
        await service.send_password_reset_email(
            to_email="user@example.com",
            user_name="user@example.com",
            raw_token="xyz789token",
        )
    mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# Tests d'intégration AuthService (DB réelle, SMTP mocké)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_verification_token(db_session: AsyncSession) -> None:
    """L'inscription crée un EmailVerificationToken valide en DB."""
    payload = schemas.RegisterRequest(
        email="newuser@example.com",
        password="SecurePass123",
        phone_number="0700000002",
    )

    with patch(_PATCH_SEND, new_callable=AsyncMock):
        user = await AuthService(db_session).register(payload)

    stmt = select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()

    assert token is not None
    assert token.used_at is None
    assert token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_reset_password_success(db_session: AsyncSession) -> None:
    """Flow complet reset : token créé → reset_password → password changé, token marqué utilisé."""
    user = await _create_user(db_session, "reset@example.com")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    reset_repo = PasswordResetTokenRepository(db_session)
    await reset_repo.create(user_id=user.id, token_hash=token_hash, expires_at=expires_at)

    await AuthService(db_session).reset_password(raw_token, "NewPassword456")

    await db_session.refresh(user)
    assert verify_password("NewPassword456", user.password_hash)

    db_token = await reset_repo.get_by_hash(token_hash)
    assert db_token is not None
    assert db_token.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_invalid_token_raises(db_session: AsyncSession) -> None:
    """Token inexistant → ValidationError."""
    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session).reset_password("nonexistent_token", "NewPassword456")


@pytest.mark.asyncio
async def test_reset_password_used_token_raises(db_session: AsyncSession) -> None:
    """Token déjà utilisé → ValidationError."""
    user = await _create_user(db_session, "used@example.com")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    reset_repo = PasswordResetTokenRepository(db_session)
    db_token = await reset_repo.create(
        user_id=user.id, token_hash=token_hash, expires_at=expires_at
    )
    await reset_repo.mark_used(db_token)

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session).reset_password(raw_token, "NewPassword456")


@pytest.mark.asyncio
async def test_reset_password_expired_token_raises(db_session: AsyncSession) -> None:
    """Token expiré → ValidationError."""
    user = await _create_user(db_session, "expired@example.com")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) - timedelta(hours=2)  # dans le passé

    reset_repo = PasswordResetTokenRepository(db_session)
    await reset_repo.create(user_id=user.id, token_hash=token_hash, expires_at=expires_at)

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session).reset_password(raw_token, "NewPassword456")


@pytest.mark.asyncio
async def test_send_password_reset_unknown_email_is_silent(db_session: AsyncSession) -> None:
    """Email inconnu → pas d'exception, pas d'email envoyé."""
    with patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send:
        await AuthService(db_session).send_password_reset("unknown@example.com")  # type: ignore[arg-type]

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_password_reset_known_email_sends(db_session: AsyncSession) -> None:
    """Email connu → token créé en DB + SMTP appelé."""
    user = await _create_user(db_session, "known@example.com")

    with patch(_PATCH_SEND, new_callable=AsyncMock) as mock_send:
        await AuthService(db_session).send_password_reset(user.email)  # type: ignore[arg-type]

    mock_send.assert_called_once()

    stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()
    assert token is not None
    assert token.used_at is None
