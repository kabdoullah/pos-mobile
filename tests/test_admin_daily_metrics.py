"""Série quotidienne du tableau de bord admin (GET /admin/metrics/daily)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import create_numbered_store, make_sale

_Admin = tuple[AsyncClient, dict[str, str]]


@pytest.mark.asyncio
async def test_daily_series_has_one_point_per_day_with_zeros(admin_client: _Admin) -> None:
    client, headers = admin_client

    data = (await client.get("/api/v1/admin/metrics/daily?days=7", headers=headers)).json()

    assert len(data) == 7
    today = datetime.now(UTC).date()  # Africa/Abidjan = UTC+0
    assert data[-1]["day"] == today.isoformat()
    assert data[0]["day"] == (today - timedelta(days=6)).isoformat()
    assert all(p["new_users"] == 0 and p["sales_count"] == 0 for p in data)
    assert Decimal(data[0]["sales_amount"]) == Decimal("0")


@pytest.mark.asyncio
async def test_daily_series_on_known_dataset(
    admin_client: _Admin, db_session: AsyncSession
) -> None:
    client, headers = admin_client
    now = datetime.now(UTC)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = max(midnight, now - timedelta(minutes=1))
    two_days_ago = midnight - timedelta(days=2) + timedelta(hours=10)

    _, a = await create_numbered_store(db_session, 1, created_at=two_days_ago)
    _, b = await create_numbered_store(db_session, 2, created_at=now - timedelta(days=60))
    db_session.add_all(
        [
            make_sale(a, "1000.00", today),
            make_sale(a, "500.00", today),
            make_sale(b, "300.00", today),
            make_sale(b, "700.00", two_days_ago),
            make_sale(b, "9999.00", now - timedelta(days=50)),
        ]
    )
    await db_session.commit()

    data = (await client.get("/api/v1/admin/metrics/daily?days=7", headers=headers)).json()
    by_day = {p["day"]: p for p in data}
    t = by_day[midnight.date().isoformat()]
    d2 = by_day[(midnight - timedelta(days=2)).date().isoformat()]

    assert (t["active_stores"], t["sales_count"]) == (2, 3)
    assert Decimal(t["sales_amount"]) == Decimal("1800.00")
    assert (d2["active_stores"], d2["sales_count"], d2["new_stores"]) == (1, 1, 1)
    assert Decimal(d2["sales_amount"]) == Decimal("700.00")
    assert sum(p["sales_count"] for p in data) == 4
    assert sum(p["new_stores"] for p in data) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("days", [6, 91])
async def test_daily_days_bounds(admin_client: _Admin, days: int) -> None:
    client, headers = admin_client
    response = await client.get(f"/api/v1/admin/metrics/daily?days={days}", headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_daily_requires_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/metrics/daily")).status_code == 401
