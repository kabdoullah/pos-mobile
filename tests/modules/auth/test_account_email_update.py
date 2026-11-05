"""Ajout / correction de l'email du compte (comptes créés sans email, fautes de frappe)."""

from datetime import UTC, datetime
from itertools import count

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import EmailService
from app.core.exceptions import ConflictError, ForbiddenError, ValidationError
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.auth.service import AuthService
from app.modules.stores.models import Store
from tests.factories import FakeEmailSender, auth_headers

_PASSWORD = "secret123"
_phones = count(1)


async def _user(db: AsyncSession, email: str | None, *, verified: bool = False) -> User:
    user = User(
        phone_number=f"+22507{next(_phones):08d}",
        email=email,
        password_hash=hash_password(_PASSWORD),
        email_verified_at=datetime.now(UTC) if verified else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def _token_from_link(body: str) -> str:
    return body.split("/auth/verify-email#token=", 1)[1].split(maxsplit=1)[0]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


async def test_legacy_account_adds_email_and_gets_link(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await _user(db_session, None)

    updated = await AuthService(db_session, email_service).update_email(
        user.id, "awa@example.com", _PASSWORD
    )

    assert updated.email == "awa@example.com"
    assert updated.email_verified_at is None
    assert [m["to_email"] for m in email_sender.sent] == ["awa@example.com"]


async def test_typo_correction_invalidates_old_link(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await _user(db_session, "awa@exmaple.com")
    svc = AuthService(db_session, email_service)
    await svc.resend_verification(user.id)
    old_link = _token_from_link(email_sender.sent[0]["text_body"])

    await svc.update_email(user.id, "awa@example.com", _PASSWORD)

    with pytest.raises(ValidationError):
        await svc.verify_email(old_link)
    await svc.verify_email(_token_from_link(email_sender.sent[1]["text_body"]))
    assert user.email == "awa@example.com"
    assert user.email_verified_at is not None


async def test_same_email_only_resends_link(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await _user(db_session, "same@example.com")

    await AuthService(db_session, email_service).update_email(
        user.id, "same@example.com", _PASSWORD
    )

    assert len(email_sender.sent) == 1
    assert user.email == "same@example.com"


async def test_wrong_password_is_forbidden(
    db_session: AsyncSession, email_service: EmailService, email_sender: FakeEmailSender
) -> None:
    user = await _user(db_session, None)

    with pytest.raises(ForbiddenError):
        await AuthService(db_session, email_service).update_email(
            user.id, "awa@example.com", "wrong-pass"
        )
    assert user.email is None
    assert email_sender.sent == []


async def test_verified_email_cannot_be_replaced(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    user = await _user(db_session, "verified@example.com", verified=True)

    with pytest.raises(ConflictError, match="verified email cannot be changed"):
        await AuthService(db_session, email_service).update_email(
            user.id, "other@example.com", _PASSWORD
        )
    assert user.email == "verified@example.com"


async def test_email_of_another_account_is_conflict(
    db_session: AsyncSession, email_service: EmailService
) -> None:
    await _user(db_session, "taken@example.com")
    user = await _user(db_session, None)

    with pytest.raises(ConflictError) as exc_info:
        await AuthService(db_session, email_service).update_email(
            user.id, "taken@example.com", _PASSWORD
        )
    assert exc_info.value.field == "email"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


async def test_put_me_email_requires_auth(client: AsyncClient) -> None:
    resp = await client.put(
        "/api/v1/users/me/email", json={"email": "a@example.com", "password": _PASSWORD}
    )
    assert resp.status_code == 401


async def test_put_me_email_lowercases_and_returns_profile(
    client: AsyncClient, db_session: AsyncSession, email_sender: FakeEmailSender
) -> None:
    user = await _user(db_session, None)
    store = Store(owner_id=user.id, name="Boutique")
    db_session.add(store)
    await db_session.flush()

    resp = await client.put(
        "/api/v1/users/me/email",
        json={"email": "Awa.Kone@Example.com", "password": _PASSWORD},
        headers=auth_headers(user.id, store.id),
    )

    assert resp.status_code == 200
    assert resp.json()["email"] == "awa.kone@example.com"
    assert resp.json()["email_verified_at"] is None
    assert email_sender.sent[0]["to_email"] == "awa.kone@example.com"


async def test_register_with_capitalized_email_is_stored_lowercase(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Avant : 500 (contrainte chk_users_email_lowercase) dès qu'une majuscule était saisie."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "phone_number": "+2250700000777",
            "password": _PASSWORD,
            "email": "Awa.Kone@Example.com",
        },
    )

    assert resp.status_code == 201
    user = await db_session.get(User, resp.json()["user_id"])
    assert user is not None
    assert user.email == "awa.kone@example.com"
