"""Vérification d'adresse email : confirmation par token, renvoi, page du lien."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailService
from app.core.exceptions import ValidationError
from app.modules.auth.models import EmailVerificationToken, User
from app.modules.auth.repository import EmailVerificationTokenRepository
from app.modules.auth.service import AuthService
from tests.factories import FakeEmailSender, auth_headers, create_user, create_user_with_store


async def _issue_token(
    db: AsyncSession, user: User, *, expires_in: timedelta = timedelta(hours=24)
) -> tuple[str, EmailVerificationToken]:
    raw = secrets.token_urlsafe(32)
    token = await EmailVerificationTokenRepository(db).create(
        user_id=user.id,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + expires_in,
    )
    return raw, token


def _token_from_link(body: str) -> str:
    return body.split("/auth/verify-email#token=", 1)[1].split(maxsplit=1)[0]


# ---------------------------------------------------------------------------
# AuthService.verify_email
# ---------------------------------------------------------------------------


async def test_verify_email_marks_user_verified_and_consumes_token(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    user = await create_user(db_session, "verify-ok@example.com")
    raw, token = await _issue_token(db_session, user)

    await AuthService(db_session, email_service).verify_email(raw)

    assert user.email_verified_at is not None
    assert token.used_at is not None


async def test_verify_email_rejects_unknown_token(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session, email_service).verify_email("unknown-token")


async def test_verify_email_rejects_used_token(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    user = await create_user(db_session, "verify-used@example.com")
    raw, _ = await _issue_token(db_session, user)
    svc = AuthService(db_session, email_service)
    await svc.verify_email(raw)

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await svc.verify_email(raw)


async def test_verify_email_rejects_expired_token(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    user = await create_user(db_session, "verify-expired@example.com")
    raw, _ = await _issue_token(db_session, user, expires_in=timedelta(seconds=-1))

    with pytest.raises(ValidationError, match="Invalid or expired token"):
        await AuthService(db_session, email_service).verify_email(raw)
    assert user.email_verified_at is None


# ---------------------------------------------------------------------------
# AuthService.resend_verification
# ---------------------------------------------------------------------------


async def test_resend_verification_invalidates_previous_link(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await create_user(db_session, "resend@example.com")
    old_raw, _ = await _issue_token(db_session, user)
    svc = AuthService(db_session, email_service)

    await svc.resend_verification(user.id)

    assert len(email_sender.sent) == 1
    with pytest.raises(ValidationError):
        await svc.verify_email(old_raw)
    await svc.verify_email(_token_from_link(email_sender.sent[0]["text_body"]))
    assert user.email_verified_at is not None


async def test_resend_verification_noop_when_already_verified(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await create_user(db_session, "already@example.com")
    user.email_verified_at = datetime.now(UTC)
    await db_session.flush()

    await AuthService(db_session, email_service).resend_verification(user.id)

    assert email_sender.sent == []
    stmt = select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    assert (await db_session.execute(stmt)).scalars().all() == []


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


async def test_verify_email_endpoint_then_reset_is_sent(
    client: AsyncClient, db_session: AsyncSession, email_sender: FakeEmailSender
) -> None:
    """Parcours complet : inscription → lien de vérification → reset de mot de passe envoyé."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "phone_number": "+2250700000501",
            "password": "secret123",
            "email": "flow@example.com",
        },
    )
    assert resp.status_code == 201

    await client.post("/api/v1/auth/forgot-password", json={"email": "flow@example.com"})
    assert len(email_sender.sent) == 1  # seulement la vérification : email pas encore vérifié

    raw = _token_from_link(email_sender.sent[0]["text_body"])
    resp = await client.post("/api/v1/auth/verify-email", json={"token": raw})
    assert resp.status_code == 204

    await client.post("/api/v1/auth/forgot-password", json={"email": "flow@example.com"})
    assert len(email_sender.sent) == 2
    assert "/auth/reset-password#token=" in email_sender.sent[1]["text_body"]


async def test_verify_email_endpoint_invalid_token_is_422(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/verify-email", json={"token": "nope"})
    assert resp.status_code == 422


async def test_resend_verification_requires_auth(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/resend-verification")
    assert resp.status_code == 401


async def test_resend_verification_endpoint_sends_email(
    client: AsyncClient, db_session: AsyncSession, email_sender: FakeEmailSender
) -> None:
    user, store = await create_user_with_store(db_session, "resend-http@example.com")

    resp = await client.post(
        "/api/v1/auth/resend-verification", headers=auth_headers(user.id, store.id)
    )

    assert resp.status_code == 204
    assert len(email_sender.sent) == 1
    assert email_sender.sent[0]["to_email"] == "resend-http@example.com"


async def test_me_exposes_email_verification_state(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await create_user_with_store(db_session, "me-verif@example.com")

    resp = await client.get("/api/v1/users/me", headers=auth_headers(user.id, store.id))

    assert resp.status_code == 200
    assert resp.json()["email_verified_at"] is None


async def test_verify_email_page_never_echoes_token(client: AsyncClient) -> None:
    token = "secret-verify-token-123"

    response = await client.get("/auth/verify-email", params={"token": token})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert token not in response.text
    assert "/api/v1/auth/verify-email" in response.text
