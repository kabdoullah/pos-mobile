"""Liste des comptes commerçants du backoffice admin (GET /admin/users)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from tests.factories import DUMMY_HASH, create_numbered_store

_Admin = tuple[AsyncClient, dict[str, str]]


async def _user_without_store(db: AsyncSession, n: int, **fields: Any) -> User:
    user = User(
        phone_number=f"+2250500{n:05d}",
        email=f"nostore{n}@test.com",
        password_hash=DUMMY_HASH,
        **fields,
    )
    db.add(user)
    await db.flush()
    return user


def _phones(data: dict[str, Any]) -> list[str]:
    return [i["phone_number"] for i in data["items"]]


@pytest.mark.asyncio
async def test_users_list_fields_and_store_filter(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    owner, store = await create_numbered_store(db_session, 1, name="Chez Awa")
    owner.email_verified_at = datetime.now(UTC)
    lone = await _user_without_store(db_session, 1, display_name="Koffi")
    await db_session.commit()

    all_users = (await client.get("/api/v1/admin/users", headers=headers)).json()
    without = (await client.get("/api/v1/admin/users?store=without", headers=headers)).json()
    with_store = (await client.get("/api/v1/admin/users?store=with", headers=headers)).json()

    assert all_users["total"] == 2
    item = next(i for i in all_users["items"] if i["phone_number"] == owner.phone_number)
    assert item["store_id"] == str(store.id)
    assert item["store_name"] == "Chez Awa"
    assert item["email_verified"] is True
    assert item["is_active"] is True
    assert _phones(without) == [lone.phone_number]
    assert without["items"][0]["store_id"] is None
    assert without["items"][0]["display_name"] == "Koffi"
    assert _phones(with_store) == [owner.phone_number]


@pytest.mark.asyncio
async def test_users_search_phone_email_name(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    await create_numbered_store(db_session, 1)
    lone = await _user_without_store(db_session, 2, display_name="Mariam")
    await db_session.commit()

    async def search(term: str) -> list[str]:
        resp = await client.get("/api/v1/admin/users", params={"search": term}, headers=headers)
        return _phones(resp.json())

    assert await search("0500000") == [lone.phone_number]
    assert await search("NOSTORE2@") == [lone.phone_number]
    assert await search("mari") == [lone.phone_number]
    assert await search("100%") == []


@pytest.mark.asyncio
async def test_users_sorted_newest_first_and_paginated(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    now = datetime.now(UTC)
    for n in range(3):
        await _user_without_store(db_session, n, created_at=now - timedelta(days=n))
    await db_session.commit()

    page = (await client.get("/api/v1/admin/users?limit=2&offset=1", headers=headers)).json()

    assert page["total"] == 3
    assert _phones(page) == ["+225050000001", "+225050000002"]


@pytest.mark.asyncio
async def test_metrics_counts_users_without_store(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    await create_numbered_store(db_session, 1)
    await _user_without_store(db_session, 1)
    await _user_without_store(db_session, 2)
    await db_session.commit()

    data = (await client.get("/api/v1/admin/metrics", headers=headers)).json()

    assert data["users_without_store"] == 2


@pytest.mark.asyncio
async def test_users_requires_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/users")).status_code == 401
