"""Tests des politiques RLS additionnelles du backoffice plateforme.

Le flag de session `app.is_platform_admin = 'on'` ouvre en lecture stores et
sales (et en UPDATE stores) ; sans lui, l'isolation par tenant reste intacte.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sales.models import Sale
from tests.factories import create_user_with_store
from tests.test_rls_isolation import _reset_store_context, _set_store_context


@pytest.mark.asyncio
async def test_admin_flag_sees_all_stores(db_session: AsyncSession) -> None:
    await _reset_store_context(db_session)
    await create_user_with_store(db_session, "admin-a@test.com")
    await create_user_with_store(db_session, "admin-b@test.com")

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'on'"))

    count = (await db_session.execute(text("SELECT count(*) FROM stores"))).scalar_one()
    assert count == 2


@pytest.mark.asyncio
async def test_tenant_without_flag_still_isolated(db_session: AsyncSession) -> None:
    await _reset_store_context(db_session)
    _, store_a = await create_user_with_store(db_session, "iso-a@test.com")
    _, store_b = await create_user_with_store(db_session, "iso-b@test.com")
    db_session.add(
        Sale(
            id=uuid4(),
            store_id=store_b.id,
            total_amount=Decimal("1000.00"),
            vat_amount=Decimal("0.00"),
            payment_method="cash",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    await _set_store_context(db_session, store_a.id)

    rows = (await db_session.execute(text("SELECT id FROM stores"))).fetchall()
    assert [r.id for r in rows] == [store_a.id]
    sales_b = (
        await db_session.execute(
            text("SELECT count(*) FROM sales WHERE store_id = :sid"),
            {"sid": str(store_b.id)},
        )
    ).scalar_one()
    assert sales_b == 0


@pytest.mark.asyncio
async def test_admin_flag_can_update_suspension(db_session: AsyncSession) -> None:
    await _reset_store_context(db_session)
    await create_user_with_store(db_session, "upd-a@test.com")
    _, store_b = await create_user_with_store(db_session, "upd-b@test.com")

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'on'"))

    result = await db_session.execute(
        text("UPDATE stores SET suspended_at = now() WHERE id = :sid"),
        {"sid": str(store_b.id)},
    )
    assert result.rowcount == 1
    suspended_at = (
        await db_session.execute(
            text("SELECT suspended_at FROM stores WHERE id = :sid"), {"sid": str(store_b.id)}
        )
    ).scalar_one()
    assert suspended_at is not None


@pytest.mark.asyncio
async def test_admin_flag_cannot_modify_sales(db_session: AsyncSession) -> None:
    await _reset_store_context(db_session)
    _, store = await create_user_with_store(db_session, "sales-mod@test.com")
    db_session.add(
        Sale(
            id=uuid4(),
            store_id=store.id,
            total_amount=Decimal("1000.00"),
            vat_amount=Decimal("0.00"),
            payment_method="cash",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text("SET LOCAL app.is_platform_admin = 'on'"))

    updated = await db_session.execute(text("UPDATE sales SET total_amount = 1"))
    deleted = await db_session.execute(text("DELETE FROM sales"))
    assert updated.rowcount == 0
    assert deleted.rowcount == 0
    await db_session.execute(text("RESET ROLE"))
    assert (await db_session.execute(text("SELECT count(*) FROM sales"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_no_flag_no_tenant_context_sees_no_store(db_session: AsyncSession) -> None:
    await _reset_store_context(db_session)
    await create_user_with_store(db_session, "nocontext@test.com")

    await db_session.execute(text("SET LOCAL ROLE pos_app"))

    assert (await db_session.execute(text("SELECT count(*) FROM stores"))).scalar_one() == 0
