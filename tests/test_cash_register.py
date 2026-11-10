"""Tests des sessions de caisse par appareil (ADR-0015)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
            "counted_amount = :counted, discrepancy_amount = :discrepancy, "
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
