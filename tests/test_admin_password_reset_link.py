"""Lien de reset généré par le support (POST /admin/users/{id}/password-reset-link, ADR-0014)."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from tests.factories import DUMMY_HASH, create_numbered_store

_Admin = tuple[AsyncClient, dict[str, str]]
_REASON = "Identité vérifiée par appel au numéro du compte"


def _url(user_id: object) -> str:
    return f"/api/v1/admin/users/{user_id}/password-reset-link"


@pytest.mark.asyncio
async def test_link_resets_password_of_unverified_account(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    owner, _ = await create_numbered_store(db_session, 1)  # email non vérifié
    await db_session.commit()

    response = await client.post(_url(owner.id), json={"reason": _REASON}, headers=headers)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    link = response.json()["link"]
    assert "/auth/reset-password#token=" in link
    token = link.split("#token=", 1)[1]

    reset = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "Nouveau-mdp-123"},
    )
    assert reset.status_code == 204
    login = await client.post(
        "/api/v1/auth/login",
        json={"phone_number": owner.phone_number, "password": "Nouveau-mdp-123"},
    )
    assert login.status_code == 200

    reused = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "Encore-autre-456"},
    )
    assert reused.status_code == 422


@pytest.mark.asyncio
async def test_works_for_account_without_email_and_is_audited(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    user = User(phone_number="+2250500000001", email=None, password_hash=DUMMY_HASH)
    db_session.add(user)
    await db_session.commit()

    response = await client.post(_url(user.id), json={"reason": _REASON}, headers=headers)
    audit = (await client.get("/api/v1/admin/audit-log", headers=headers)).json()

    assert response.status_code == 200
    entry = audit["items"][0]
    assert entry["action"] == "user_password_reset_link"
    assert entry["user_id"] == str(user.id)
    assert entry["user_phone"] == "+2250500000001"
    assert entry["store_id"] is None
    assert entry["reason"] == _REASON
    assert response.json()["link"].split("#token=", 1)[1] not in str(audit)


@pytest.mark.asyncio
async def test_entry_appears_in_store_history(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    owner, store = await create_numbered_store(db_session, 1, name="Chez Awa")
    await db_session.commit()

    await client.post(_url(owner.id), json={"reason": _REASON}, headers=headers)
    detail = (await client.get(f"/api/v1/admin/stores/{store.id}", headers=headers)).json()

    assert [(h["action"], h["store_name"]) for h in detail["history"]] == [
        ("user_password_reset_link", "Chez Awa")
    ]


@pytest.mark.asyncio
async def test_unknown_user_is_404(admin_client: _Admin) -> None:
    client, headers = admin_client
    response = await client.post(_url(uuid4()), json={"reason": _REASON}, headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_inactive_user_is_409_and_not_audited(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    owner, _ = await create_numbered_store(db_session, 1)
    owner.is_active = False
    await db_session.commit()

    response = await client.post(_url(owner.id), json={"reason": _REASON}, headers=headers)
    audit = (await client.get("/api/v1/admin/audit-log", headers=headers)).json()

    assert response.status_code == 409
    assert audit["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"reason": "ok"}])
async def test_reason_is_required(
    admin_client: _Admin, db_session: AsyncSession, body: dict[str, str]
) -> None:
    client, headers = admin_client
    owner, _ = await create_numbered_store(db_session, 1)
    await db_session.commit()

    response = await client.post(_url(owner.id), json=body, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_requires_admin(client: AsyncClient) -> None:
    response = await client.post(_url(uuid4()), json={"reason": _REASON})
    assert response.status_code == 401
