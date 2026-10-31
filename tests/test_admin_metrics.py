"""Tests des indicateurs plateforme du backoffice admin."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.stores.models import Store
from tests.factories import create_numbered_store, make_sale


async def _store(db: AsyncSession, n: int, created_at: datetime, suspended: bool = False) -> Store:
    _, store = await create_numbered_store(db, n, created_at, suspended)
    return store


@pytest.mark.asyncio
async def test_metrics_on_known_dataset(
    admin_client: tuple[AsyncClient, dict[str, str]], db_session: AsyncSession
) -> None:
    client, headers = admin_client
    now = datetime.now(UTC)
    # Minuit Abidjan (UTC+0) du jour courant ; "aujourd'hui" = [minuit, now].
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = max(midnight, now - timedelta(minutes=1))

    a = await _store(db_session, 1, now - timedelta(days=30))
    b = await _store(db_session, 2, now - timedelta(days=30))
    await _store(db_session, 3, now - timedelta(days=1))
    d = await _store(db_session, 4, now - timedelta(days=30), suspended=True)
    db_session.add_all(
        [
            make_sale(a, "1500.00", today),
            make_sale(a, "2500.00", today),
            make_sale(b, "700.00", now - timedelta(days=20)),
            make_sale(d, "1000.00", today),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/admin/metrics", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["stores_total"] == 4
    assert data["stores_new_7d"] == 1
    assert data["stores_active_7d"] == 1
    assert data["stores_inactive_14d"] == 1
    assert data["stores_suspended"] == 1
    assert data["sales_today_count"] == 3
    assert Decimal(data["sales_today_amount"]) == Decimal("5000.00")
    assert data["sales_7d_count"] == 3
    assert Decimal(data["sales_7d_amount"]) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_metrics_empty_platform(
    admin_client: tuple[AsyncClient, dict[str, str]],
) -> None:
    client, headers = admin_client
    data = (await client.get("/api/v1/admin/metrics", headers=headers)).json()
    assert data["stores_total"] == 0
    assert Decimal(data["sales_7d_amount"]) == Decimal("0")


@pytest.mark.asyncio
async def test_metrics_requires_admin(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_definition_edges(
    admin_client: tuple[AsyncClient, dict[str, str]], db_session: AsyncSession
) -> None:
    """Pin les bornes : aujourd'hui vs 7 j, suspendue exclue des inactives, fenêtre 14 j."""
    client, headers = admin_client
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = max(midnight, now - timedelta(minutes=1))

    e = await _store(db_session, 1, now - timedelta(days=30))
    await _store(db_session, 2, now - timedelta(days=30), suspended=True)  # F, sans vente
    g = await _store(db_session, 3, now - timedelta(days=30))
    db_session.add_all(
        [
            make_sale(e, "100.00", today),
            make_sale(e, "200.00", now - timedelta(days=2) - timedelta(minutes=1)),
            make_sale(g, "300.00", now - timedelta(days=10)),
        ]
    )
    await db_session.commit()

    data = (await client.get("/api/v1/admin/metrics", headers=headers)).json()

    assert data["stores_total"] == 3
    assert data["stores_new_7d"] == 0
    assert data["stores_active_7d"] == 1
    assert data["stores_inactive_14d"] == 0
    assert data["stores_suspended"] == 1
    assert data["sales_today_count"] == 1
    assert Decimal(data["sales_today_amount"]) == Decimal("100.00")
    assert data["sales_7d_count"] == 2
    assert Decimal(data["sales_7d_amount"]) == Decimal("300.00")
