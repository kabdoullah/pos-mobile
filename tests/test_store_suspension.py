"""Tests du blocage des boutiques suspendues (login, refresh, requêtes tenant)."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_refresh_token, hash_password
from app.modules.stores.models import Store
from tests.test_sync import _create_store, _create_user, _headers, _sale_payload

_PASSWORD = "motdepasse123"
_SUPPORT = "+2250700000000"


@pytest.fixture(autouse=True)
def _support_contact() -> Iterator[None]:
    with patch.object(settings, "support_contact", _SUPPORT):
        yield


async def _setup(db: AsyncSession, email: str) -> tuple[Any, Any]:
    await db.execute(text("RESET ROLE"))
    user = await _create_user(db, email)
    user.password_hash = hash_password(_PASSWORD)
    store = await _create_store(db, user.id)
    await db.flush()
    return user, store


async def _set_suspended(db: AsyncSession, store_id: Any, suspended: bool) -> None:
    await db.execute(text("RESET ROLE"))
    await db.execute(
        text(
            "UPDATE stores SET suspended_at = "
            + ("now()" if suspended else "NULL")
            + " WHERE id = :sid"
        ),
        {"sid": str(store_id)},
    )
    # La session de test est partagée avec l'app : invalide la boutique en cache.
    store = await db.get(Store, store_id)
    if store is not None:
        await db.refresh(store)


def _assert_suspended(response: Any) -> None:
    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "STORE_SUSPENDED"
    assert body["details"]["support_contact"] == _SUPPORT


async def test_suspended_store_blocked_on_get_me(client: AsyncClient, db_session: AsyncSession):
    user, store = await _setup(db_session, "susp-me@example.com")
    await _set_suspended(db_session, store.id, True)

    response = await client.get("/api/v1/stores/me", headers=_headers(user.id, store.id))

    _assert_suspended(response)


async def test_token_issued_before_suspension_blocked_on_sync(
    client: AsyncClient, db_session: AsyncSession
):
    user, store = await _setup(db_session, "susp-sync@example.com")
    headers = _headers(user.id, store.id)
    await _set_suspended(db_session, store.id, True)

    response = await client.post(
        "/api/v1/sync/sales", json={"sales": [_sale_payload(sale_id=uuid4())]}, headers=headers
    )

    _assert_suspended(response)
    await db_session.execute(text("RESET ROLE"))
    count = (await db_session.execute(text("SELECT count(*) FROM sales"))).scalar_one()
    assert count == 0


async def test_suspended_store_login_refused(client: AsyncClient, db_session: AsyncSession):
    user, store = await _setup(db_session, "susp-login@example.com")
    await _set_suspended(db_session, store.id, True)

    response = await client.post(
        "/api/v1/auth/login",
        json={"phone_number": user.phone_number, "password": _PASSWORD},
    )

    _assert_suspended(response)


async def test_suspended_store_refresh_refused(client: AsyncClient, db_session: AsyncSession):
    user, store = await _setup(db_session, "susp-refresh@example.com")
    await _set_suspended(db_session, store.id, True)

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": create_refresh_token(user.id)}
    )

    _assert_suspended(response)


async def test_reactivated_store_works_again(client: AsyncClient, db_session: AsyncSession):
    user, store = await _setup(db_session, "susp-react@example.com")
    await _set_suspended(db_session, store.id, True)
    await _set_suspended(db_session, store.id, False)

    response = await client.get("/api/v1/stores/me", headers=_headers(user.id, store.id))

    assert response.status_code == 200


async def test_other_errors_have_no_details_key(client: AsyncClient, db_session: AsyncSession):
    user, store = await _setup(db_session, "susp-404@example.com")

    response = await client.get(f"/api/v1/products/{uuid4()}", headers=_headers(user.id, store.id))

    assert response.status_code == 404
    assert "details" not in response.json()
