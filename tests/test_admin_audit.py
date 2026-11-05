"""Journal des actions admin (admin_audit_log, GET /admin/audit-log)."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from tests.factories import ADMIN_EMAIL, ADMIN_PASSWORD, create_admin, create_numbered_store

_Admin = tuple[AsyncClient, dict[str, str]]


@pytest.fixture
def _admin_secret() -> Iterator[None]:
    with patch.object(settings, "admin_jwt_secret_key", SecretStr("a" * 48)):
        yield


async def _audit(client: AsyncClient, headers: dict[str, str], query: str = "") -> dict:  # type: ignore[type-arg]
    return (await client.get(f"/api/v1/admin/audit-log{query}", headers=headers)).json()


@pytest.mark.asyncio
@pytest.mark.usefixtures("_admin_secret")
async def test_successful_login_is_logged_failed_is_not(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_admin(db_session)
    url = "/api/v1/admin/auth/login"
    await client.post(url, json={"email": ADMIN_EMAIL, "password": "wrong"})
    token = (
        await client.post(url, json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    ).json()["access_token"]

    data = await _audit(client, {"Authorization": f"Bearer {token}"})

    assert [(e["action"], e["admin_email"]) for e in data["items"]] == [("login", ADMIN_EMAIL)]


@pytest.mark.asyncio
async def test_suspend_and_reactivate_are_logged_and_filterable(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, a = await create_numbered_store(db_session, 1, name="Chez Awa")
    _, b = await create_numbered_store(db_session, 2)
    await db_session.commit()

    await client.post(
        f"/api/v1/admin/stores/{a.id}/suspend", json={"reason": "Fraude"}, headers=headers
    )
    await client.post(f"/api/v1/admin/stores/{a.id}/reactivate", headers=headers)
    await client.post(f"/api/v1/admin/stores/{b.id}/suspend", json={}, headers=headers)

    everything = await _audit(client, headers)
    only_a = await _audit(client, headers, f"?store_id={a.id}")
    paged = await _audit(client, headers, "?limit=1&offset=1")

    assert everything["total"] == 3
    assert [e["action"] for e in everything["items"]] == [
        "store_suspended",
        "store_reactivated",
        "store_suspended",
    ]
    assert only_a["total"] == 2
    assert only_a["items"][1]["store_name"] == "Chez Awa"
    assert only_a["items"][1]["reason"] == "Fraude"
    assert [e["action"] for e in paged["items"]] == ["store_reactivated"]


@pytest.mark.asyncio
async def test_entry_survives_store_deletion(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1, name="Partie")
    await db_session.commit()
    await client.post(f"/api/v1/admin/stores/{store.id}/suspend", json={}, headers=headers)
    await db_session.commit()

    await db_session.execute(text("RESET ROLE"))
    await db_session.execute(text("DELETE FROM stores WHERE id = :id"), {"id": store.id})
    await db_session.commit()

    data = await _audit(client, headers)
    assert data["items"][0]["store_id"] == str(store.id)
    assert data["items"][0]["store_name"] == "Partie"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "statement",
    ["UPDATE admin_audit_log SET reason = 'x'", "DELETE FROM admin_audit_log"],
)
async def test_audit_log_is_immutable(
    admin_client: _Admin, db_session: AsyncSession, statement: str
) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()
    await client.post(f"/api/v1/admin/stores/{store.id}/suspend", json={}, headers=headers)
    await db_session.commit()

    with pytest.raises(DBAPIError, match="immutable"):
        await db_session.execute(text(statement))


@pytest.mark.asyncio
async def test_deleting_admin_keeps_entries(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()
    await client.post(f"/api/v1/admin/stores/{store.id}/suspend", json={}, headers=headers)
    await db_session.commit()

    await db_session.execute(text("RESET ROLE"))
    await db_session.execute(text("DELETE FROM platform_admins"))
    await db_session.commit()

    row = (
        await db_session.execute(text("SELECT admin_id, admin_email FROM admin_audit_log"))
    ).one()
    assert row.admin_id is None
    assert row.admin_email == "metrics-admin@test.ci"


@pytest.mark.asyncio
async def test_audit_requires_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/audit-log")).status_code == 401
