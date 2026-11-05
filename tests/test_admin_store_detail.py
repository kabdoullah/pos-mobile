"""Fiche boutique du backoffice admin (GET /admin/stores/{id})."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Product
from tests.factories import create_numbered_store, make_sale

_Admin = tuple[AsyncClient, dict[str, str]]


@pytest.mark.asyncio
async def test_store_detail_fields_and_counters(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    now = datetime.now(UTC)
    user, store = await create_numbered_store(db_session, 1, name="Chez Awa")
    user.display_name = "Awa"
    store.address = "Cocody"
    db_session.add_all(
        [
            Product(store_id=store.id, name="Pain", selling_price=Decimal("200.00")),
            Product(store_id=store.id, name="Lait", selling_price=Decimal("500.00")),
            Product(
                store_id=store.id,
                name="Ancien",
                selling_price=Decimal("100.00"),
                deleted_at=now,
            ),
            make_sale(store, "1500.00", now - timedelta(days=1)),
            make_sale(store, "500.00", now - timedelta(days=29)),
            make_sale(store, "9000.00", now - timedelta(days=40)),
        ]
    )
    await db_session.commit()

    response = await client.get(f"/api/v1/admin/stores/{store.id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Chez Awa"
    assert data["address"] == "Cocody"
    assert data["owner_display_name"] == "Awa"
    assert data["owner_phone"] == user.phone_number
    assert data["owner_is_active"] is True
    assert data["products_count"] == 2
    assert data["sales_count"] == 3
    assert data["sales_30d_count"] == 2
    assert Decimal(data["sales_30d_amount"]) == Decimal("2000.00")
    assert data["history"] == []


@pytest.mark.asyncio
async def test_store_detail_without_sales(admin_client: _Admin, db_session: AsyncSession) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()

    data = (await client.get(f"/api/v1/admin/stores/{store.id}", headers=headers)).json()

    assert data["products_count"] == 0
    assert data["sales_30d_count"] == 0
    assert Decimal(data["sales_30d_amount"]) == Decimal("0")
    assert data["last_sale_at"] is None


@pytest.mark.asyncio
async def test_store_detail_history_after_suspension(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    _, store = await create_numbered_store(db_session, 1)
    await db_session.commit()

    await client.post(
        f"/api/v1/admin/stores/{store.id}/suspend", json={"reason": "Impayé"}, headers=headers
    )
    await client.post(f"/api/v1/admin/stores/{store.id}/reactivate", headers=headers)
    data = (await client.get(f"/api/v1/admin/stores/{store.id}", headers=headers)).json()

    assert [(h["action"], h["reason"]) for h in data["history"]] == [
        ("store_reactivated", None),
        ("store_suspended", "Impayé"),
    ]
    assert data["history"][0]["admin_email"] == "metrics-admin@test.ci"


@pytest.mark.asyncio
async def test_store_detail_unknown_is_404(admin_client: _Admin) -> None:
    client, headers = admin_client
    response = await client.get(f"/api/v1/admin/stores/{uuid4()}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_store_detail_requires_admin(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/admin/stores/{uuid4()}")
    assert response.status_code == 401
