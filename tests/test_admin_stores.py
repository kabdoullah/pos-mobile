"""Tests de la liste des boutiques, de la suspension et de la réactivation (admin)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.stores.models import Store
from tests.factories import auth_headers, create_numbered_store, make_sale

_Admin = tuple[AsyncClient, dict[str, str]]


async def _dataset(db: AsyncSession) -> dict[str, Store]:
    """Jeu de Task 4 : A active, B inactive, C récente, D suspendue."""
    now = datetime.now(UTC)
    _, a = await create_numbered_store(db, 1, now - timedelta(days=30))
    _, b = await create_numbered_store(db, 2, now - timedelta(days=30))
    _, c = await create_numbered_store(db, 3, now - timedelta(days=1))
    _, d = await create_numbered_store(db, 4, now - timedelta(days=30), suspended=True)
    db.add_all(
        [
            make_sale(a, "1500.00", now - timedelta(minutes=1)),
            make_sale(b, "700.00", now - timedelta(days=20)),
            make_sale(d, "1000.00", now - timedelta(minutes=1)),
        ]
    )
    await db.commit()
    return {"A": a, "B": b, "C": c, "D": d}


def _ids(response_json: dict[str, Any]) -> list[str]:
    return [item["id"] for item in response_json["items"]]


@pytest.mark.asyncio
async def test_list_stores_fields(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    now = datetime.now(UTC)
    user, store = await create_numbered_store(db_session, 1)
    latest = now - timedelta(hours=1)
    db_session.add_all(
        [
            make_sale(store, "100.00", now - timedelta(days=3)),
            make_sale(store, "100.00", now - timedelta(days=2)),
            make_sale(store, "100.00", latest),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/stores", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["id"] == str(store.id)
    assert item["name"] == store.name
    assert item["sales_count"] == 3
    assert datetime.fromisoformat(item["last_sale_at"]) == latest
    assert item["owner_phone"] == user.phone_number
    assert item["suspended_at"] is None


@pytest.mark.asyncio
async def test_list_store_without_sales(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    await create_numbered_store(db_session, 1)
    await db_session.commit()

    item = (await client.get("/api/v1/admin/stores", headers=headers)).json()["items"][0]

    assert item["last_sale_at"] is None
    assert item["sales_count"] == 0


@pytest.mark.asyncio
async def test_list_filters_status_and_inactive(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    s = await _dataset(db_session)

    suspended = await client.get("/api/v1/admin/stores?status=suspended", headers=headers)
    active = await client.get("/api/v1/admin/stores?status=active", headers=headers)
    inactive = await client.get("/api/v1/admin/stores?inactive=true", headers=headers)

    assert _ids(suspended.json()) == [str(s["D"].id)]
    assert set(_ids(active.json())) == {str(s[k].id) for k in "ABC"}
    assert _ids(inactive.json()) == [str(s["B"].id)]
    assert inactive.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_sort(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    s = await _dataset(db_session)

    by_sale = await client.get("/api/v1/admin/stores?sort=last_sale", headers=headers)
    by_created = await client.get("/api/v1/admin/stores?sort=created", headers=headers)

    # Dernière vente : A et D (il y a 1 min), B (20 j), C sans vente. À égalité de
    # dernière vente, created_at DESC puis id : A (créée avant) et D ont la même
    # date de création, l'ordre entre eux est fixé par id.
    ab = sorted([str(s["A"].id), str(s["D"].id)])
    assert _ids(by_sale.json()) == [*ab, str(s["B"].id), str(s["C"].id)]
    # Par création : C (1 j) d'abord, puis A, B, D (30 j, départagés par id).
    rest = sorted(str(s[k].id) for k in "ABD")
    assert _ids(by_created.json()) == [str(s["C"].id), *rest]


@pytest.mark.asyncio
async def test_list_search_by_name_and_phone(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, a = await create_numbered_store(db_session, 1, name="Chez Awa")
    await create_numbered_store(db_session, 2, name="Chez Koffi")
    await db_session.commit()

    by_name = await client.get("/api/v1/admin/stores?search=awa", headers=headers)
    by_phone = await client.get("/api/v1/admin/stores?search=070000002", headers=headers)

    assert _ids(by_name.json()) == [str(a.id)]
    assert by_phone.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_search_escapes_wildcards(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, first = await create_numbered_store(db_session, 1, name="Chez 100%")
    await create_numbered_store(db_session, 2, name="Chez 1000")
    await create_numbered_store(db_session, 3, name="Chez a_b")
    await create_numbered_store(db_session, 4, name="Chez axb")
    await db_session.commit()

    percent = await client.get("/api/v1/admin/stores", params={"search": "100%"}, headers=headers)
    underscore = await client.get("/api/v1/admin/stores", params={"search": "a_b"}, headers=headers)
    backslash = await client.get("/api/v1/admin/stores", params={"search": "\\"}, headers=headers)

    assert _ids(percent.json()) == [str(first.id)]
    assert underscore.json()["total"] == 1
    assert backslash.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_pagination(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    for n in range(25):
        await create_numbered_store(db_session, n)
    await db_session.commit()

    page = await client.get("/api/v1/admin/stores?limit=20&offset=20", headers=headers)

    assert page.status_code == 200
    assert len(page.json()["items"]) == 5
    assert page.json()["total"] == 25
    assert (await client.get("/api/v1/admin/stores?limit=101", headers=headers)).status_code == 422
    assert (await client.get("/api/v1/admin/stores?offset=-1", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_list_requires_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/stores")).status_code == 401


@pytest.mark.asyncio
async def test_suspend_then_merchant_blocked(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    user, store = await create_numbered_store(db_session, 1)
    await db_session.commit()
    merchant = auth_headers(user.id, store.id)

    response = await client.post(
        f"/api/v1/admin/stores/{store.id}/suspend", json={"reason": "Impayé"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["suspension_reason"] == "Impayé"
    assert response.json()["suspended_at"] is not None
    await db_session.commit()
    await db_session.execute(text("RESET ROLE"))
    blocked = await client.get("/api/v1/stores/me", headers=merchant)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "STORE_SUSPENDED"


@pytest.mark.asyncio
async def test_suspend_twice_keeps_first_date(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()
    url = f"/api/v1/admin/stores/{store.id}/suspend"

    first = (await client.post(url, json={"reason": "Un"}, headers=headers)).json()
    second = (await client.post(url, json={"reason": "Deux"}, headers=headers)).json()

    assert second["suspended_at"] == first["suspended_at"]
    assert second["suspension_reason"] == "Deux"


@pytest.mark.asyncio
async def test_suspend_without_body_reason(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/admin/stores/{store.id}/suspend", json={}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["suspension_reason"] is None
    assert response.json()["suspended_at"] is not None


@pytest.mark.asyncio
async def test_resuspend_without_reason_keeps_reason_and_date(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()
    url = f"/api/v1/admin/stores/{store.id}/suspend"

    first = (await client.post(url, json={"reason": "Impayé"}, headers=headers)).json()
    second = (await client.post(url, json={}, headers=headers)).json()

    assert second["suspension_reason"] == "Impayé"
    assert second["suspended_at"] == first["suspended_at"]


@pytest.mark.asyncio
async def test_reactivate(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    user, store = await create_numbered_store(db_session, 1, suspended=True)
    store.suspension_reason = "Impayé"
    await db_session.commit()

    response = await client.post(f"/api/v1/admin/stores/{store.id}/reactivate", headers=headers)

    assert response.status_code == 200
    assert response.json()["suspended_at"] is None
    assert response.json()["suspension_reason"] is None
    await db_session.commit()
    await db_session.execute(text("RESET ROLE"))
    ok = await client.get("/api/v1/stores/me", headers=auth_headers(user.id, store.id))
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_suspend_unknown_store(admin_client: _Admin) -> None:
    client, headers = admin_client
    unknown: UUID = uuid4()

    suspend = await client.post(f"/api/v1/admin/stores/{unknown}/suspend", json={}, headers=headers)
    reactivate = await client.post(f"/api/v1/admin/stores/{unknown}/reactivate", headers=headers)

    assert suspend.status_code == 404
    assert reactivate.status_code == 404


@pytest.mark.asyncio
async def test_suspend_reason_too_long(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/admin/stores/{store.id}/suspend", json={"reason": "x" * 501}, headers=headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_suspension_requires_admin(client: AsyncClient) -> None:
    uid = uuid4()
    assert (await client.post(f"/api/v1/admin/stores/{uid}/suspend", json={})).status_code == 401
    assert (await client.post(f"/api/v1/admin/stores/{uid}/reactivate")).status_code == 401
