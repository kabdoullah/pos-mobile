"""Tests des sessions de caisse par appareil (ADR-0015)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_register.models import CashMovement, CashSession
from app.modules.cash_register.repository import CashSessionRepository
from app.modules.cash_register.service import CashSessionService
from app.modules.returns.schemas import SaleReturnCreate
from app.modules.returns.service import ReturnService
from app.modules.sales.schemas import SaleCreate
from app.modules.sales.service import SaleService
from tests.test_sync import _create_store, _create_user

# ---------------------------------------------------------------------------
# Contraintes de base de données (migration cash_register)
# ---------------------------------------------------------------------------


async def _store(db: AsyncSession, email: str) -> tuple[UUID, UUID]:
    """Crée un utilisateur et sa boutique, retourne (user_id, store_id)."""
    user = await _create_user(db, email)
    store = await _create_store(db, user.id)
    return user.id, store.id


async def _insert_open_session(
    db: AsyncSession, store_id: UUID, device_id: UUID, user_id: UUID | None = None
) -> UUID:
    session_id = uuid4()
    await db.execute(
        text(
            "INSERT INTO cash_sessions "
            "(id, store_id, device_id, status, opening_amount, opened_at, opened_by) "
            "VALUES (:id, :store_id, :device_id, 'open', 10000, :opened_at, :user_id)"
        ),
        {
            "id": session_id,
            "store_id": store_id,
            "device_id": device_id,
            "opened_at": datetime.now(UTC) - timedelta(hours=8),
            "user_id": user_id,
        },
    )
    return session_id


async def _close_session(
    db: AsyncSession,
    session_id: UUID,
    *,
    expected: str = "10000",
    counted: str = "10000",
    discrepancy: str = "0",
    note: str | None = None,
) -> None:
    await db.execute(
        text(
            "UPDATE cash_sessions SET status = 'closed', expected_amount = :expected, "
            "client_expected_amount = :expected, counted_amount = :counted, discrepancy_amount = :discrepancy, "
            "closing_note = :note, closed_at = :closed_at, closure_recorded_at = now() "
            "WHERE id = :id"
        ),
        {
            "id": session_id,
            "expected": expected,
            "counted": counted,
            "discrepancy": discrepancy,
            "note": note,
            "closed_at": datetime.now(UTC),
        },
    )


async def _insert_movement(
    db: AsyncSession, store_id: UUID, session_id: UUID, type_: str, reason: str
) -> UUID:
    movement_id = uuid4()
    await db.execute(
        text(
            "INSERT INTO cash_movements (id, store_id, session_id, type, reason, amount, created_at) "
            "VALUES (:id, :store_id, :session_id, :type, :reason, 2000, now())"
        ),
        {
            "id": movement_id,
            "store_id": store_id,
            "session_id": session_id,
            "type": type_,
            "reason": reason,
        },
    )
    return movement_id


async def test_two_open_sessions_same_device_violate_unique_index(
    db_session: AsyncSession,
) -> None:
    _, store_id = await _store(db_session, "cash-unique@test.com")
    device = uuid4()
    await _insert_open_session(db_session, store_id, device)

    with pytest.raises(IntegrityError, match="uq_cash_sessions_open_per_device"):
        async with db_session.begin_nested():
            await _insert_open_session(db_session, store_id, device)


async def test_open_sessions_on_two_devices_are_allowed(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-two-devices@test.com")
    await _insert_open_session(db_session, store_id, uuid4())
    await _insert_open_session(db_session, store_id, uuid4())

    count = (
        await db_session.execute(text("SELECT COUNT(*) FROM cash_sessions WHERE status = 'open'"))
    ).scalar()
    assert count == 2


async def test_device_can_reopen_after_close(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-reopen@test.com")
    device = uuid4()
    first = await _insert_open_session(db_session, store_id, device)
    await _close_session(db_session, first)

    await _insert_open_session(db_session, store_id, device)


async def test_closed_session_cannot_be_updated(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-closed-update@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _close_session(db_session, session_id)

    with pytest.raises(DBAPIError, match="closed"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE cash_sessions SET closing_note = 'x' WHERE id = :id"),
                {"id": session_id},
            )


async def test_cash_session_cannot_be_deleted(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-delete@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(DBAPIError, match="DELETE not allowed"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("DELETE FROM cash_sessions WHERE id = :id"), {"id": session_id}
            )


async def test_cash_movement_is_immutable(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-movement-immutable@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _insert_movement(db_session, store_id, session_id, "cash_out", "expense")

    with pytest.raises(DBAPIError, match="immutable"):
        async with db_session.begin_nested():
            await db_session.execute(text("UPDATE cash_movements SET amount = 1"))
    with pytest.raises(DBAPIError, match="immutable"):
        async with db_session.begin_nested():
            await db_session.execute(text("DELETE FROM cash_movements"))


async def test_closed_with_discrepancy_requires_note(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-discrepancy-note@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(IntegrityError, match="chk_cash_sessions_note_on_discrepancy"):
        async with db_session.begin_nested():
            await _close_session(
                db_session, session_id, expected="10000", counted="9500", discrepancy="-500"
            )

    await _close_session(
        db_session,
        session_id,
        expected="10000",
        counted="9500",
        discrepancy="-500",
        note="Monnaie rendue en trop",
    )


async def test_closed_discrepancy_must_equal_counted_minus_expected(
    db_session: AsyncSession,
) -> None:
    _, store_id = await _store(db_session, "cash-discrepancy-calc@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(IntegrityError, match="chk_cash_sessions_state"):
        async with db_session.begin_nested():
            await _close_session(
                db_session,
                session_id,
                expected="10000",
                counted="9500",
                discrepancy="500",
                note="faux",
            )


async def test_open_session_cannot_carry_closing_fields(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-open-closing-fields@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(IntegrityError, match="chk_cash_sessions_state"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE cash_sessions SET counted_amount = 100 WHERE id = :id"),
                {"id": session_id},
            )


async def test_cash_out_reason_must_match_type(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-reason-type@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(IntegrityError, match="chk_cash_movements_reason"):
        async with db_session.begin_nested():
            await _insert_movement(db_session, store_id, session_id, "cash_in", "expense")

    await _insert_movement(db_session, store_id, session_id, "cash_in", "top_up")


async def test_cash_tables_are_isolated_by_store(db_session: AsyncSession) -> None:
    _, store_a = await _store(db_session, "cash-rls-a@test.com")
    _, store_b = await _store(db_session, "cash-rls-b@test.com")
    session_a = await _insert_open_session(db_session, store_a, uuid4())
    await _insert_movement(db_session, store_a, session_a, "cash_in", "float")
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_b}'"))
    sessions = (await db_session.execute(text("SELECT COUNT(*) FROM cash_sessions"))).scalar()
    movements = (await db_session.execute(text("SELECT COUNT(*) FROM cash_movements"))).scalar()
    assert (sessions, movements) == (0, 0)


async def test_purge_store_removes_cash_register_data(db_session: AsyncSession) -> None:
    """La suppression de compte (ADR-0011) purge aussi les sessions clôturées."""
    _, store_id = await _store(db_session, "cash-purge@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _insert_movement(db_session, store_id, session_id, "cash_out", "withdrawal")
    await _close_session(db_session, session_id, expected="8000", counted="8000")
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))
    await db_session.execute(text("SELECT purge_store(:id)"), {"id": store_id})

    sessions = (await db_session.execute(text("SELECT COUNT(*) FROM cash_sessions"))).scalar()
    assert sessions == 0


async def test_closed_session_requires_client_expected_amount(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "cash-client-expected@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _close_session(db_session, session_id)

    other = await _insert_open_session(db_session, store_id, uuid4())
    with pytest.raises(IntegrityError, match="chk_cash_sessions_state"):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "UPDATE cash_sessions SET status = 'closed', expected_amount = 0, "
                    "counted_amount = 0, discrepancy_amount = 0, closed_at = now(), "
                    "closure_recorded_at = now() WHERE id = :id"
                ),
                {"id": other},
            )


async def test_movement_cannot_reference_session_of_another_store(
    db_session: AsyncSession,
) -> None:
    _, store_a = await _store(db_session, "cash-xstore-mvt-a@test.com")
    _, store_b = await _store(db_session, "cash-xstore-mvt-b@test.com")
    session_a = await _insert_open_session(db_session, store_a, uuid4())

    with pytest.raises(IntegrityError, match="fk_cash_movements_session"):
        async with db_session.begin_nested():
            await _insert_movement(db_session, store_b, session_a, "cash_in", "top_up")


async def test_sale_cannot_reference_session_of_another_store(db_session: AsyncSession) -> None:
    _, store_a = await _store(db_session, "cash-xstore-sale-a@test.com")
    _, store_b = await _store(db_session, "cash-xstore-sale-b@test.com")
    session_a = await _insert_open_session(db_session, store_a, uuid4())
    insert_sale = text(
        "INSERT INTO sales (id, store_id, total_amount, payment_method, created_at, "
        "cash_session_id) VALUES (:id, :store_id, 1000, 'cash', now(), :session_id)"
    )

    with pytest.raises(IntegrityError, match="fk_sales_cash_session"):
        async with db_session.begin_nested():
            await db_session.execute(
                insert_sale, {"id": uuid4(), "store_id": store_b, "session_id": session_a}
            )

    # Même boutique : accepté ; sans session (NULL) : non vérifié.
    await db_session.execute(
        insert_sale, {"id": uuid4(), "store_id": store_a, "session_id": session_a}
    )
    await db_session.execute(insert_sale, {"id": uuid4(), "store_id": store_b, "session_id": None})


async def test_rls_rejects_session_inserted_for_another_store(db_session: AsyncSession) -> None:
    _, store_a = await _store(db_session, "cash-rls-check-a@test.com")
    _, store_b = await _store(db_session, "cash-rls-check-b@test.com")
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_a}'"))
    with pytest.raises(DBAPIError, match="row-level security"):
        async with db_session.begin_nested():
            await _insert_open_session(db_session, store_b, uuid4())


# ---------------------------------------------------------------------------
# Solde théorique (spec §3) — helpers, contexte tenant (pos_app + RLS)
# ---------------------------------------------------------------------------


async def _tenant(db: AsyncSession, email: str) -> tuple[UUID, UUID]:
    """Crée user + boutique, puis bascule la transaction dans le contexte tenant."""
    user = await _create_user(db, email)
    store = await _create_store(db, user.id)
    await db.commit()
    await db.execute(text("SET LOCAL ROLE pos_app"))
    await db.execute(text(f"SET LOCAL app.current_store_id = '{store.id}'"))
    return user.id, store.id


async def _open_session(
    db: AsyncSession, store_id: UUID, user_id: UUID, opening: str = "10000"
) -> CashSession:
    session = CashSession(
        id=uuid4(),
        store_id=store_id,
        device_id=uuid4(),
        status="open",
        opening_amount=Decimal(opening),
        opened_at=datetime.now(UTC),
        opened_by=user_id,
    )
    assert await CashSessionRepository(db).insert_session(session)
    return session


def _sale(
    session_id: UUID | None,
    total: str,
    payment_method: str = "cash",
    *,
    cash_amount: str | None = None,
    mobile_money_amount: str | None = None,
) -> SaleCreate:
    """Vente d'une ligne au prix `total`, rattachée à `session_id`."""
    return SaleCreate.model_validate(
        {
            "id": str(uuid4()),
            "items": [
                {
                    "id": str(uuid4()),
                    "product_name_at_sale": "Article",
                    "unit_price_at_sale": total,
                    "quantity": 1,
                    "line_total": total,
                }
            ],
            "total_amount": total,
            "payment_method": payment_method,
            "cash_amount": cash_amount,
            "mobile_money_amount": mobile_money_amount,
            "created_at": datetime.now(UTC).isoformat(),
            "cash_session_id": str(session_id) if session_id else None,
        }
    )


def _return(
    sale: Any, session_id: UUID, amount: str, refund_method: str = "cash"
) -> SaleReturnCreate:
    """Retour total de la (seule) ligne de `sale`."""
    item = sale.items[0]
    return SaleReturnCreate.model_validate(
        {
            "id": str(uuid4()),
            "sale_id": str(sale.id),
            "reason": "defective",
            "refund_method": refund_method,
            "refund_amount": amount,
            "created_at": datetime.now(UTC).isoformat(),
            "cash_session_id": str(session_id),
            "items": [
                {
                    "id": str(uuid4()),
                    "sale_item_id": str(item.id),
                    "quantity": 1,
                    "condition": "damaged",
                    "refund_amount": amount,
                }
            ],
        }
    )


# ---------------------------------------------------------------------------
# Solde théorique
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_balance_without_operations_is_opening_amount(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-empty@test.com")
    session = await _open_session(db_session, store_id, user_id)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("10000")
    assert summary.opening_amount == Decimal("10000")
    assert (summary.cash_sales, summary.cash_sales_count) == (Decimal("0"), 0)
    assert summary.mobile_money_sales == Decimal("0")
    assert (summary.cash_in, summary.cash_out, summary.cash_refunds) == (0, 0, 0)
    assert summary.late_impact == Decimal("0")
    assert summary.server_recalculated is False


@pytest.mark.asyncio
async def test_cash_sale_counts_total(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-sale@test.com")
    session = await _open_session(db_session, store_id, user_id)
    await SaleService(db_session).create_sale(store_id, _sale(session.id, "3000"), user_id)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("13000")
    assert (summary.cash_sales, summary.cash_sales_count) == (Decimal("3000"), 1)


@pytest.mark.asyncio
async def test_mobile_money_sale_is_excluded(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-momo@test.com")
    session = await _open_session(db_session, store_id, user_id)
    await SaleService(db_session).create_sale(
        store_id, _sale(session.id, "5000", "mobile_money_wave"), user_id
    )

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("10000")
    assert summary.mobile_money_sales == Decimal("5000")
    assert (summary.cash_sales, summary.cash_sales_count) == (Decimal("0"), 0)


@pytest.mark.asyncio
async def test_mixed_sale_counts_cash_part_only(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-mixed@test.com")
    session = await _open_session(db_session, store_id, user_id)
    payload = _sale(session.id, "8000", "mixed", cash_amount="3000", mobile_money_amount="5000")
    await SaleService(db_session).create_sale(store_id, payload, user_id)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("13000")
    assert summary.cash_sales == Decimal("3000")
    assert summary.mobile_money_sales == Decimal("5000")


@pytest.mark.asyncio
async def test_cash_refund_decreases_and_mobile_refund_does_not(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-refund@test.com")
    session = await _open_session(db_session, store_id, user_id)
    sales = SaleService(db_session)
    first, _ = await sales.create_sale(store_id, _sale(session.id, "1000"), user_id)
    second, _ = await sales.create_sale(store_id, _sale(session.id, "500"), user_id)
    returns = ReturnService(db_session)
    await returns.create_return(store_id, _return(first, session.id, "1000"), user_id)
    await returns.create_return(
        store_id, _return(second, session.id, "500", "mobile_money_orange"), user_id
    )

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.cash_refunds == Decimal("1000")
    # 10000 + 1500 de ventes espèces - 1000 remboursés en espèces.
    assert summary.expected_amount == Decimal("10500")


@pytest.mark.asyncio
async def test_cash_in_adds_and_cash_out_subtracts(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-movements@test.com")
    session = await _open_session(db_session, store_id, user_id)
    repo = CashSessionRepository(db_session)
    for type_, reason, amount in (("cash_in", "top_up", "2000"), ("cash_out", "expense", "500")):
        movement = CashMovement(
            id=uuid4(),
            store_id=store_id,
            session_id=session.id,
            type=type_,
            reason=reason,
            amount=Decimal(amount),
            created_at=datetime.now(UTC),
            created_by=user_id,
        )
        assert await repo.insert_movement(movement)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert (summary.cash_in, summary.cash_out) == (Decimal("2000"), Decimal("500"))
    assert summary.expected_amount == Decimal("11500")


@pytest.mark.asyncio
async def test_sales_of_another_session_are_ignored(db_session: AsyncSession) -> None:
    user_id, store_id = await _tenant(db_session, "cash-other@test.com")
    session = await _open_session(db_session, store_id, user_id)
    other = await _open_session(db_session, store_id, user_id)
    sales = SaleService(db_session)
    await sales.create_sale(store_id, _sale(other.id, "4000"), user_id)
    await sales.create_sale(store_id, _sale(None, "2000"), user_id)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("10000")
    assert summary.cash_sales_count == 0


@pytest.mark.asyncio
async def test_closed_session_keeps_frozen_amount_and_reports_late_impact(
    db_session: AsyncSession,
) -> None:
    """Une vente arrivée après la clôture n'entre pas dans le montant figé."""
    user_id, store_id = await _tenant(db_session, "cash-closed@test.com")
    now = datetime.now(UTC)
    session = CashSession(
        id=uuid4(),
        store_id=store_id,
        device_id=uuid4(),
        status="closed",
        opening_amount=Decimal("10000"),
        opened_at=now,
        opened_by=user_id,
        expected_amount=Decimal("10000"),
        client_expected_amount=Decimal("9000"),
        counted_amount=Decimal("10000"),
        discrepancy_amount=Decimal("0"),
        closed_at=now,
        closure_recorded_at=now,
    )
    assert await CashSessionRepository(db_session).insert_session(session)
    await SaleService(db_session).create_sale(store_id, _sale(session.id, "2500"), user_id)

    summary = await CashSessionService(db_session).compute_balance(session)

    assert summary.expected_amount == Decimal("10000")
    assert summary.late_impact == Decimal("2500")
    assert summary.server_recalculated is True
