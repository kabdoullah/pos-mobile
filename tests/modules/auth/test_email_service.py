"""Tests du service email et de l'intégration token-email dans AuthService."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import (
    BrevoEmailSender,
    EmailSendError,
    EmailService,
    NullEmailSender,
    get_email_service,
)
from app.core.exceptions import ValidationError
from app.core.security import hash_password, verify_password
from app.modules.auth import schemas
from app.modules.auth.models import EmailVerificationToken, PasswordResetToken, User
from app.modules.auth.repository import PasswordResetTokenRepository, UserRepository
from app.modules.auth.service import AuthService
from tests.factories import FakeEmailSender

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PHONE_COUNTER = iter(range(1000, 9999))


async def _create_user(db: AsyncSession, email: str, *, verified: bool = True) -> User:
    user = User(
        phone_number=f"+22507{next(_PHONE_COUNTER):07d}",
        email=email,
        password_hash=hash_password("OldPassword1"),
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    return await UserRepository(db).create(user)


# ---------------------------------------------------------------------------
# Tests unitaires EmailService (transport factice, pas de DB)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_verification_email_sends_once(
    email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """send_verification_email délègue au transport exactement une fois."""
    await email_service.send_verification_email(
        to_email="user@example.com",
        user_name="user@example.com",
        raw_token="abc123token",
    )
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to_email"] == "user@example.com"
    sent = email_sender.sent[0]
    for body in (sent["html_body"], sent["text_body"]):
        assert "/auth/verify-email#token=abc123token" in body
        assert "?token=" not in body


@pytest.mark.asyncio
async def test_send_password_reset_email_sends_once(
    email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """send_password_reset_email délègue au transport exactement une fois."""
    await email_service.send_password_reset_email(
        to_email="user@example.com",
        user_name="user@example.com",
        raw_token="xyz789token",
    )
    assert len(email_sender.sent) == 1


@pytest.mark.asyncio
async def test_password_reset_link_keeps_token_out_of_query(
    email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Le token est dans le fragment, jamais dans la query (logs d'accès)."""
    await email_service.send_password_reset_email(
        to_email="user@example.com", user_name="user@example.com", raw_token="xyz789token"
    )
    sent = email_sender.sent[0]
    for body in (sent["html_body"], sent["text_body"]):
        assert "/auth/reset-password#token=xyz789token" in body
        assert "?token=" not in body


def _brevo_sender() -> BrevoEmailSender:
    return BrevoEmailSender(
        api_key="xkeysib-test", from_email="expediteur@example.com", from_name="Ma Caisse"
    )


@pytest.mark.asyncio
async def test_brevo_sender_posts_to_brevo() -> None:
    """BrevoEmailSender appelle l'API Brevo avec la clé et le corps attendus."""
    post = AsyncMock(return_value=httpx.Response(201, json={"messageId": "<id>"}))
    with patch.object(httpx.AsyncClient, "post", post):
        await _brevo_sender().send("user@example.com", "Sujet", "<p>html</p>", "texte")

    post.assert_awaited_once()
    assert post.call_args.args[0] == "https://api.brevo.com/v3/smtp/email"
    assert post.call_args.kwargs["headers"] == {"api-key": "xkeysib-test"}
    assert post.call_args.kwargs["json"] == {
        "sender": {"name": "Ma Caisse", "email": "expediteur@example.com"},
        "to": [{"email": "user@example.com"}],
        "subject": "Sujet",
        "htmlContent": "<p>html</p>",
        "textContent": "texte",
    }


@pytest.mark.asyncio
async def test_brevo_sender_raises_on_brevo_error() -> None:
    """Une erreur Brevo remonte avec son statut et son corps (cause exacte)."""
    body = '{"code":"unauthorized","message":"Sender not valid"}'
    post = AsyncMock(return_value=httpx.Response(400, text=body))
    with patch.object(httpx.AsyncClient, "post", post), pytest.raises(EmailSendError) as exc:
        await _brevo_sender().send("user@example.com", "Sujet", "<p>html</p>", "texte")
    assert exc.value.status_code == 400
    assert exc.value.body == body


def test_get_email_service_uses_brevo_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "email_enabled", True)
    monkeypatch.setattr(settings, "brevo_api_key", SecretStr("xkeysib-test"))
    assert isinstance(get_email_service()._sender, BrevoEmailSender)


@pytest.mark.asyncio
async def test_get_email_service_sends_nothing_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "email_enabled", False)
    service = get_email_service()
    assert isinstance(service._sender, NullEmailSender)
    post = AsyncMock()
    with patch.object(httpx.AsyncClient, "post", post):
        await service.send_verification_email("user@example.com", "user", "tok")
    post.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests d'intégration AuthService (DB réelle, transport factice)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_verification_token(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """L'inscription crée un EmailVerificationToken valide en DB."""
    payload = schemas.RegisterRequest(
        phone_number="+2250700000002",
        password="SecurePass123",
        email="newuser@example.com",
    )

    user = await AuthService(db_session, email_service).register(payload)
    assert len(email_sender.sent) == 1

    stmt = select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()

    assert token is not None
    assert token.used_at is None
    assert token.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_register_succeeds_when_email_send_fails(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Best-effort : un échec SMTP ne bloque pas l'inscription, le token reste en DB."""
    payload = schemas.RegisterRequest(
        phone_number="+2250700000003",
        password="SecurePass123",
        email="smtpdown@example.com",
    )

    email_sender.error = Exception("provider down")
    user = await AuthService(db_session, email_service).register(payload)

    assert user.id is not None

    stmt = select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()
    assert token is not None


@pytest.mark.asyncio
async def test_send_password_reset_succeeds_when_email_send_fails(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Best-effort : échec SMTP ne lève pas, le token reset reste en DB."""
    user = await _create_user(db_session, "resetdown@example.com")

    email_sender.error = Exception("provider down")
    await AuthService(db_session, email_service).send_password_reset(user.email)  # type: ignore[arg-type]

    stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()
    assert token is not None


@pytest.mark.asyncio
async def test_reset_password_success(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    """Flow complet reset : token créé → reset_password → password changé, token marqué utilisé."""
    user = await _create_user(db_session, "reset@example.com")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=1)

    reset_repo = PasswordResetTokenRepository(db_session)
    await reset_repo.create(user_id=user.id, token_hash=token_hash, expires_at=expires_at)

    await AuthService(db_session, email_service).reset_password(raw_token, "NewPassword456")

    await db_session.refresh(user)
    assert verify_password("NewPassword456", user.password_hash)

    db_token = await reset_repo.get_by_hash(token_hash)
    assert db_token is not None
    assert db_token.used_at is not None


@pytest.mark.asyncio
async def test_reset_password_invalid_token_raises(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    """Token inexistant → ValidationError."""
    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session, email_service).reset_password(
            "nonexistent_token", "NewPassword456"
        )


@pytest.mark.asyncio
async def test_reset_password_used_token_raises(
    db_session: AsyncSession, email_service: EmailService
) -> None:
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
        await AuthService(db_session, email_service).reset_password(raw_token, "NewPassword456")


@pytest.mark.asyncio
async def test_reset_password_expired_token_raises(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    """Token expiré → ValidationError."""
    user = await _create_user(db_session, "expired@example.com")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(UTC) - timedelta(hours=2)  # dans le passé

    reset_repo = PasswordResetTokenRepository(db_session)
    await reset_repo.create(user_id=user.id, token_hash=token_hash, expires_at=expires_at)

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session, email_service).reset_password(raw_token, "NewPassword456")


@pytest.mark.asyncio
async def test_send_password_reset_unknown_email_is_silent(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Email inconnu → pas d'exception, pas d'email envoyé."""
    await AuthService(db_session, email_service).send_password_reset("unknown@example.com")  # type: ignore[arg-type]

    assert email_sender.sent == []


@pytest.mark.asyncio
async def test_send_password_reset_known_email_sends(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Email connu et vérifié → token créé en DB + SMTP appelé."""
    user = await _create_user(db_session, "known@example.com")

    await AuthService(db_session, email_service).send_password_reset(user.email)  # type: ignore[arg-type]

    assert len(email_sender.sent) == 1

    stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    token = (await db_session.execute(stmt)).scalar_one_or_none()
    assert token is not None
    assert token.used_at is None


@pytest.mark.asyncio
async def test_send_password_reset_unverified_email_is_silent(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    """Email non vérifié → aucun token ni email : un squatteur d'adresse ne reçoit rien."""
    user = await _create_user(db_session, "unverified@example.com", verified=False)

    await AuthService(db_session, email_service).send_password_reset(user.email)  # type: ignore[arg-type]

    assert email_sender.sent == []
    stmt = select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    assert (await db_session.execute(stmt)).scalar_one_or_none() is None
