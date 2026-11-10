"""Tests des sessions de caisse par appareil (ADR-0015)."""

import asyncio
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.cash_register.exceptions import CashSessionAlreadyOpenError
from app.modules.cash_register.models import CashMovement, CashSession
from app.modules.cash_register.repository import CashSessionRepository
from app.modules.cash_register.schemas import CashSessionClose, CashSessionOpen
from app.modules.cash_register.service import CashSessionService
from app.modules.returns.schemas import SaleReturnCreate
from app.modules.returns.service import ReturnService
from app.modules.sales.schemas import SaleCreate
from app.modules.sales.service import SaleService
from tests.test_sync import _create_store, _create_user, _headers

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


# ---------------------------------------------------------------------------
# API : ouverture, session active, détail, historique (spec §5.1 à §5.4)
# ---------------------------------------------------------------------------

_CASH_URL = "/api/v1/cash-sessions"


def _open_payload(
    device_id: UUID | None = None,
    amount: str = "25000",
    opened_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "device_id": str(device_id or uuid4()),
        "opening_amount": amount,
        "opening_note": "Fond de caisse",
        "opened_at": (opened_at or datetime.now(UTC)).isoformat(),
    }


async def _http_store(db: AsyncSession, email: str) -> tuple[UUID, UUID, dict[str, str]]:
    """Crée user + boutique (commit), retourne (user_id, store_id, headers)."""
    user = await _create_user(db, email)
    store = await _create_store(db, user.id)
    await db.commit()
    return user.id, store.id, _headers(user.id, store.id)


@pytest.mark.asyncio
async def test_open_session_returns_201_and_retry_returns_200(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id, _, headers = await _http_store(db_session, "cash-api-open@test.com")
    payload = _open_payload()

    created = await client.post(_CASH_URL, json=payload, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == payload["id"]
    assert body["device_id"] == payload["device_id"]
    assert body["status"] == "open"
    assert Decimal(body["opening_amount"]) == Decimal("25000")
    assert isinstance(body["opening_amount"], str)
    assert body["opening_note"] == "Fond de caisse"
    assert body["opened_by"] == str(user_id)
    for field in (
        "expected_amount",
        "client_expected_amount",
        "counted_amount",
        "discrepancy_amount",
        "closing_note",
        "closed_at",
        "closed_by",
    ):
        assert body[field] is None

    retry = await client.post(_CASH_URL, json=payload, headers=headers)
    assert retry.status_code == 200, retry.text
    assert retry.json() == body


@pytest.mark.asyncio
async def test_open_with_same_id_different_amount_is_idempotency_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-idem@test.com")
    payload = _open_payload()
    assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 201

    response = await client.post(
        _CASH_URL, json={**payload, "opening_amount": "30000"}, headers=headers
    )

    assert response.status_code == 409
    assert response.json()["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_second_open_on_same_device_is_409_already_open(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-already@test.com")
    device = uuid4()
    assert (
        await client.post(_CASH_URL, json=_open_payload(device), headers=headers)
    ).status_code == 201

    response = await client.post(_CASH_URL, json=_open_payload(device), headers=headers)

    assert response.status_code == 409
    assert response.json()["code"] == "CASH_SESSION_ALREADY_OPEN"
    # La transaction reste utilisable après le rollback du SAVEPOINT.
    other = await client.post(_CASH_URL, json=_open_payload(), headers=headers)
    assert other.status_code == 201


@pytest.mark.asyncio
async def test_concurrent_opens_on_same_device_only_one_succeeds(db_engine: Any) -> None:
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as setup:
        user_id, store_id = await _store(setup, "cash-api-concurrent@test.com")
        await setup.commit()
    device = uuid4()

    async def attempt() -> str:
        payload = CashSessionOpen.model_validate(_open_payload(device))
        async with session_maker() as db:
            await db.execute(text("SET LOCAL ROLE pos_app"))
            await db.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))
            try:
                await CashSessionService(db).open(store_id, user_id, payload)
                await db.commit()
            except CashSessionAlreadyOpenError:
                await db.rollback()
                return "already_open"
            return "created"

    results = await asyncio.gather(attempt(), attempt())

    assert sorted(results) == ["already_open", "created"]


@pytest.mark.asyncio
async def test_get_active_returns_detail_or_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-active@test.com")
    device = uuid4()

    missing = await client.get(
        f"{_CASH_URL}/active", params={"device_id": str(device)}, headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"

    payload = _open_payload(device, amount="15000")
    assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 201

    active = await client.get(
        f"{_CASH_URL}/active", params={"device_id": str(device)}, headers=headers
    )
    assert active.status_code == 200, active.text
    body = active.json()
    assert body["session"]["id"] == payload["id"]
    assert Decimal(body["summary"]["expected_amount"]) == Decimal("15000")
    assert body["summary"]["server_recalculated"] is False
    assert body["movements"] == []

    detail = await client.get(f"{_CASH_URL}/{payload['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json() == body


@pytest.mark.asyncio
async def test_history_is_paginated_newest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-history@test.com")
    now = datetime.now(UTC)
    ids = []
    for hours_ago in (3, 1, 2):
        payload = _open_payload(opened_at=now - timedelta(hours=hours_ago))
        assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 201
        ids.append(payload["id"])
    oldest, newest, middle = ids

    first = await client.get(_CASH_URL, params={"limit": 2}, headers=headers)
    assert first.status_code == 200, first.text
    page = first.json()
    assert [s["id"] for s in page["items"]] == [newest, middle]
    assert page["has_more"] is True
    assert page["next_cursor"]

    second = await client.get(
        _CASH_URL, params={"limit": 2, "cursor": page["next_cursor"]}, headers=headers
    )
    page = second.json()
    assert [s["id"] for s in page["items"]] == [oldest]
    assert page["has_more"] is False
    assert page["next_cursor"] is None


@pytest.mark.asyncio
async def test_history_filters_by_device(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-history-device@test.com")
    device = uuid4()
    mine = _open_payload(device)
    for payload in (mine, _open_payload()):
        assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 201

    response = await client.get(_CASH_URL, params={"device_id": str(device)}, headers=headers)

    assert [s["id"] for s in response.json()["items"]] == [mine["id"]]


@pytest.mark.asyncio
async def test_store_cannot_see_or_open_on_session_of_another_store(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers_a = await _http_store(db_session, "cash-api-rls-a@test.com")
    _, _, headers_b = await _http_store(db_session, "cash-api-rls-b@test.com")
    device = uuid4()
    payload = _open_payload(device)
    assert (await client.post(_CASH_URL, json=payload, headers=headers_a)).status_code == 201

    detail = await client.get(f"{_CASH_URL}/{payload['id']}", headers=headers_b)
    assert detail.status_code == 404
    assert detail.json()["code"] == "NOT_FOUND"
    active = await client.get(
        f"{_CASH_URL}/active", params={"device_id": str(device)}, headers=headers_b
    )
    assert active.status_code == 404
    history = await client.get(_CASH_URL, headers=headers_b)
    assert history.json()["items"] == []


@pytest.mark.asyncio
async def test_negative_opening_amount_and_future_opened_at_are_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-api-422@test.com")

    negative = await client.post(_CASH_URL, json=_open_payload(amount="-1"), headers=headers)
    assert negative.status_code == 422
    assert negative.json()["field"] == "opening_amount"

    future = await client.post(
        _CASH_URL,
        json=_open_payload(opened_at=datetime.now(UTC) + timedelta(minutes=10)),
        headers=headers,
    )
    assert future.status_code == 422
    assert future.json()["code"] == "VALIDATION_ERROR"

    naive = _open_payload()
    naive["opened_at"] = datetime.now().replace(tzinfo=None).isoformat()
    assert (await client.post(_CASH_URL, json=naive, headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_open_other_integrity_error_is_not_already_open(db_session: AsyncSession) -> None:
    """Seul l'index partiel donne CASH_SESSION_ALREADY_OPEN : une FK violée remonte telle quelle."""
    _, store_id = await _tenant(db_session, "cash-api-fk@test.com")
    payload = CashSessionOpen.model_validate(_open_payload())

    with pytest.raises(IntegrityError, match="fk_cash_sessions_opened_by"):
        await CashSessionService(db_session).open(store_id, uuid4(), payload)


# ---------------------------------------------------------------------------
# API : mouvements d'espèces (spec §5.5)
# ---------------------------------------------------------------------------


def _movement_payload(
    type_: str = "cash_out",
    amount: str = "3500",
    reason: str | None = None,
    note: str | None = "Sachets",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": type_,
        "reason": reason or ("supplies" if type_ == "cash_out" else "top_up"),
        "amount": amount,
        "note": note,
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
    }


async def _http_open(client: AsyncClient, headers: dict[str, str], amount: str = "10000") -> str:
    payload = _open_payload(amount=amount)
    response = await client.post(_CASH_URL, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return str(payload["id"])


async def _post_movement(
    client: AsyncClient, headers: dict[str, str], session_id: str, payload: dict[str, Any]
) -> Any:
    return await client.post(f"{_CASH_URL}/{session_id}/movements", json=payload, headers=headers)


async def _expected_amount(client: AsyncClient, headers: dict[str, str], session_id: str) -> Any:
    detail = await client.get(f"{_CASH_URL}/{session_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    return detail.json()


async def _close_via_sql(db: AsyncSession, session_id: str) -> None:
    """Clôture la session en SQL, derrière le dos de l'identity map de `db`.

    Le client HTTP partage `db` : le verrou FOR UPDATE (populate_existing)
    doit rafraîchir l'objet resté « open » en mémoire.
    """
    await _close_session(db, UUID(session_id))


@pytest.mark.asyncio
async def test_cash_in_and_out_change_balance(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id, _, headers = await _http_store(db_session, "cash-mvt-balance@test.com")
    session_id = await _http_open(client, headers)

    cash_in = _movement_payload("cash_in", "5000", note=None)
    created = await _post_movement(client, headers, session_id, cash_in)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["id"] == cash_in["id"]
    assert body["session_id"] == session_id
    assert body["type"] == "cash_in"
    assert body["reason"] == "top_up"
    assert isinstance(body["amount"], str)
    assert Decimal(body["amount"]) == Decimal("5000")
    assert body["created_by"] == str(user_id)
    assert body["synced_at"]

    cash_out = await _post_movement(
        client, headers, session_id, _movement_payload("cash_out", "3500")
    )
    assert cash_out.status_code == 201, cash_out.text

    detail = await _expected_amount(client, headers, session_id)
    assert Decimal(detail["summary"]["expected_amount"]) == Decimal("11500")
    assert Decimal(detail["summary"]["cash_in"]) == Decimal("5000")
    assert Decimal(detail["summary"]["cash_out"]) == Decimal("3500")
    assert len(detail["movements"]) == 2


@pytest.mark.asyncio
async def test_cash_out_above_balance_is_422_insufficient_cash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-mvt-insufficient@test.com")
    session_id = await _http_open(client, headers)

    response = await _post_movement(
        client, headers, session_id, _movement_payload("cash_out", "10000.01")
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "INSUFFICIENT_CASH"
    assert response.json()["field"] == "amount"
    detail = await _expected_amount(client, headers, session_id)
    assert detail["movements"] == []


@pytest.mark.asyncio
async def test_cash_out_equal_to_balance_is_allowed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-mvt-equal@test.com")
    session_id = await _http_open(client, headers)

    response = await _post_movement(
        client, headers, session_id, _movement_payload("cash_out", "10000")
    )

    assert response.status_code == 201, response.text
    detail = await _expected_amount(client, headers, session_id)
    assert Decimal(detail["summary"]["expected_amount"]) == Decimal("0")


@pytest.mark.asyncio
async def test_movement_retry_is_200_without_double_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-mvt-retry@test.com")
    session_id = await _http_open(client, headers)
    payload = _movement_payload("cash_out", "3500")

    created = await _post_movement(client, headers, session_id, payload)
    assert created.status_code == 201, created.text
    # Montant écrit autrement mais égal : retry légitime.
    retry = await _post_movement(client, headers, session_id, {**payload, "amount": "3500.00"})
    assert retry.status_code == 200, retry.text
    assert retry.json() == created.json()

    detail = await _expected_amount(client, headers, session_id)
    assert Decimal(detail["summary"]["expected_amount"]) == Decimal("6500")
    assert len(detail["movements"]) == 1

    for changed in ({"amount": "3000"}, {"type": "cash_in", "reason": "top_up"}):
        conflict = await _post_movement(client, headers, session_id, {**payload, **changed})
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    other_session = await _http_open(client, headers)
    conflict = await _post_movement(client, headers, other_session, payload)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.asyncio
async def test_movement_after_closing_time_is_409_session_closed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-mvt-closed@test.com")
    session_id = await _http_open(client, headers)
    await _close_via_sql(db_session, session_id)

    response = await _post_movement(
        client,
        headers,
        session_id,
        _movement_payload("cash_in", "1000", created_at=datetime.now(UTC) + timedelta(minutes=1)),
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "CASH_SESSION_CLOSED"


@pytest.mark.asyncio
async def test_movement_created_before_closure_arriving_late_is_accepted_and_in_late_impact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Review Focus 5 : l'argent a déjà bougé, pas de contrôle de solde sur session close."""
    _, _, headers = await _http_store(db_session, "cash-mvt-late@test.com")
    session_id = await _http_open(client, headers)
    await _close_via_sql(db_session, session_id)

    # Sortie supérieure au solde (10000) : acceptée, la session est clôturée.
    response = await _post_movement(
        client,
        headers,
        session_id,
        _movement_payload("cash_out", "12000", created_at=datetime.now(UTC) - timedelta(minutes=5)),
    )

    assert response.status_code == 201, response.text
    summary = (await _expected_amount(client, headers, session_id))["summary"]
    assert Decimal(summary["expected_amount"]) == Decimal("10000")
    assert Decimal(summary["late_impact"]) == Decimal("-12000")


@pytest.mark.asyncio
async def test_other_reason_requires_note_and_amount_must_be_positive(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-mvt-422@test.com")
    session_id = await _http_open(client, headers)

    invalid = [
        (_movement_payload("cash_out", reason="other", note=None), "note"),
        (_movement_payload("cash_in", reason="other", note="   "), "note"),
        (_movement_payload("cash_out", amount="0"), "amount"),
        (_movement_payload("cash_out", amount="-5"), "amount"),
        (_movement_payload("cash_in", reason="expense"), "reason"),
        (_movement_payload("cash_out", reason="top_up"), "reason"),
        (_movement_payload("transfer"), "type"),
        (
            _movement_payload(created_at=datetime.now(UTC) + timedelta(minutes=10)),
            "created_at",
        ),
    ]
    for payload, field in invalid:
        response = await _post_movement(client, headers, session_id, payload)
        assert response.status_code == 422, (payload, response.text)
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert response.json()["field"] == field

    ok = await _post_movement(
        client, headers, session_id, _movement_payload("cash_out", reason="other", note="Taxi")
    )
    assert ok.status_code == 201, ok.text


@pytest.mark.asyncio
async def test_movement_on_session_of_another_store_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers_a = await _http_store(db_session, "cash-mvt-rls-a@test.com")
    _, _, headers_b = await _http_store(db_session, "cash-mvt-rls-b@test.com")
    session_a = await _http_open(client, headers_a)
    payload = _movement_payload("cash_in", "1000")

    response = await _post_movement(client, headers_b, session_a, payload)
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "NOT_FOUND"
    unknown = await _post_movement(client, headers_a, str(uuid4()), _movement_payload("cash_in"))
    assert unknown.status_code == 404

    # Id de mouvement déjà pris dans une autre boutique (invisible, RLS) : conflit, pas 500.
    assert (await _post_movement(client, headers_a, session_a, payload)).status_code == 201
    session_b = await _http_open(client, headers_b)
    hidden = await _post_movement(client, headers_b, session_b, payload)
    assert hidden.status_code == 409, hidden.text
    assert hidden.json()["code"] == "IDEMPOTENCY_CONFLICT"


# ---------------------------------------------------------------------------
# API : clôture (spec §5.6, §6)
# ---------------------------------------------------------------------------


def _close_payload(
    counted: str = "10000",
    client_expected: str | None = None,
    note: str | None = None,
    closed_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "counted_amount": counted,
        "client_expected_amount": client_expected if client_expected is not None else counted,
        "closing_note": note,
        "closed_at": (closed_at or datetime.now(UTC)).isoformat(),
    }


async def _post_close(
    client: AsyncClient, headers: dict[str, str], session_id: str, payload: dict[str, Any]
) -> Any:
    return await client.post(f"{_CASH_URL}/{session_id}/close", json=payload, headers=headers)


@pytest.mark.asyncio
async def test_close_balanced_session(client: AsyncClient, db_session: AsyncSession) -> None:
    user_id, _, headers = await _http_store(db_session, "cash-close-balanced@test.com")
    session_id = await _http_open(client, headers)
    payload = _close_payload("10000.00", client_expected="10000")

    response = await _post_close(client, headers, session_id, payload)

    assert response.status_code == 200, response.text
    body = response.json()
    session = body["session"]
    assert session["status"] == "closed"
    assert Decimal(session["expected_amount"]) == Decimal("10000")
    assert Decimal(session["counted_amount"]) == Decimal("10000")
    assert Decimal(session["discrepancy_amount"]) == Decimal("0")
    assert isinstance(session["discrepancy_amount"], str)
    assert session["closing_note"] is None
    assert session["closed_by"] == str(user_id)
    assert datetime.fromisoformat(session["closed_at"]) == datetime.fromisoformat(
        payload["closed_at"]
    )
    assert Decimal(body["summary"]["expected_amount"]) == Decimal("10000")
    assert Decimal(body["summary"]["late_impact"]) == Decimal("0")
    assert body["summary"]["server_recalculated"] is False

    # L'appareil n'a plus de session active ; closure_recorded_at est posé.
    active = await client.get(
        f"{_CASH_URL}/active", params={"device_id": session["device_id"]}, headers=headers
    )
    assert active.status_code == 404
    recorded = (
        await db_session.execute(
            text("SELECT closure_recorded_at FROM cash_sessions WHERE id = :id"),
            {"id": session_id},
        )
    ).scalar()
    assert recorded is not None


@pytest.mark.asyncio
async def test_close_with_shortage_requires_note(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-close-shortage@test.com")
    session_id = await _http_open(client, headers)

    for note in (None, "   "):
        missing = await _post_close(client, headers, session_id, _close_payload("9500", note=note))
        assert missing.status_code == 422, missing.text
        assert missing.json()["code"] == "VALIDATION_ERROR"
        assert missing.json()["field"] == "closing_note"
    still_open = await _expected_amount(client, headers, session_id)
    assert still_open["session"]["status"] == "open"

    response = await _post_close(
        client, headers, session_id, _close_payload("9500", note="Monnaie rendue en trop")
    )

    assert response.status_code == 200, response.text
    session = response.json()["session"]
    assert Decimal(session["discrepancy_amount"]) == Decimal("-500")
    assert session["closing_note"] == "Monnaie rendue en trop"


@pytest.mark.asyncio
async def test_close_with_surplus_and_decimal_amounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Review Focus 3 : arithmétique Decimal exacte, aucun float."""
    _, _, headers = await _http_store(db_session, "cash-close-surplus@test.com")
    session_id = await _http_open(client, headers, amount="1000.50")
    cash_in = await _post_movement(
        client, headers, session_id, _movement_payload("cash_in", "500", note=None)
    )
    assert cash_in.status_code == 201, cash_in.text

    response = await _post_close(
        client,
        headers,
        session_id,
        _close_payload("1600.00", client_expected="1500.50", note="Excédent"),
    )

    assert response.status_code == 200, response.text
    session = response.json()["session"]
    assert Decimal(session["expected_amount"]) == Decimal("1500.50")
    assert Decimal(session["discrepancy_amount"]) == Decimal("99.50")


@pytest.mark.asyncio
async def test_server_ignores_client_expected_amount(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-close-recalc@test.com")
    session_id = await _http_open(client, headers)

    response = await _post_close(
        client, headers, session_id, _close_payload("10000", client_expected="99999")
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["session"]["expected_amount"]) == Decimal("10000")
    assert Decimal(body["session"]["client_expected_amount"]) == Decimal("99999")
    assert Decimal(body["session"]["discrepancy_amount"]) == Decimal("0")
    assert Decimal(body["summary"]["expected_amount"]) == Decimal("10000")
    assert Decimal(body["summary"]["late_impact"]) == Decimal("0")
    assert body["summary"]["server_recalculated"] is True


@pytest.mark.asyncio
async def test_close_with_negative_expected_amount(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Les remboursements espèces ne sont jamais bloqués : la clôture reste possible à -2000."""
    user_id, store_id, headers = await _http_store(db_session, "cash-close-negative@test.com")
    session_id = await _http_open(client, headers, amount="1000")
    other_session = await _http_open(client, headers)
    # Le contexte tenant (SET LOCAL) du dernier appel HTTP reste actif sur db_session.
    sale, _ = await SaleService(db_session).create_sale(
        store_id, _sale(UUID(other_session), "3000"), user_id
    )
    await ReturnService(db_session).create_return(
        store_id, _return(sale, UUID(session_id), "3000"), user_id
    )

    response = await _post_close(
        client,
        headers,
        session_id,
        _close_payload("0", client_expected="-2000", note="Remboursement sans fond"),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["session"]["expected_amount"]) == Decimal("-2000")
    assert Decimal(body["session"]["discrepancy_amount"]) == Decimal("2000")
    assert body["summary"]["server_recalculated"] is False


@pytest.mark.asyncio
async def test_close_retry_with_same_payload_returns_200_same_result(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Review Focus 2 : une clôture rejouée ne change rien et répond 200."""
    _, _, headers = await _http_store(db_session, "cash-close-retry@test.com")
    session_id = await _http_open(client, headers)
    payload = _close_payload("9500", note="Manque 500")

    first = await _post_close(client, headers, session_id, payload)
    assert first.status_code == 200, first.text
    retry = await _post_close(client, headers, session_id, payload)
    assert retry.status_code == 200, retry.text
    assert retry.json() == first.json()

    # Mêmes valeurs écrites autrement (montant, fuseau) : toujours le même retry.
    closed_at = datetime.fromisoformat(payload["closed_at"])
    same = {
        **payload,
        "counted_amount": "9500.00",
        "closed_at": closed_at.astimezone(timezone(timedelta(hours=1))).isoformat(),
    }
    again = await _post_close(client, headers, session_id, same)
    assert again.status_code == 200, again.text
    assert again.json() == first.json()


@pytest.mark.asyncio
async def test_second_close_with_different_count_is_409_session_closed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "cash-close-409@test.com")
    session_id = await _http_open(client, headers)
    payload = _close_payload("10000")
    assert (await _post_close(client, headers, session_id, payload)).status_code == 200

    closed_at = datetime.fromisoformat(payload["closed_at"])
    for changed in (
        {"counted_amount": "9000", "closing_note": "Manque"},
        {"closed_at": (closed_at + timedelta(seconds=1)).isoformat()},
    ):
        response = await _post_close(client, headers, session_id, {**payload, **changed})
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "CASH_SESSION_CLOSED"

    detail = await _expected_amount(client, headers, session_id)
    assert Decimal(detail["session"]["counted_amount"]) == Decimal("10000")


@pytest.mark.asyncio
async def test_sale_after_closure_is_in_late_impact_not_in_expected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_id, store_id, headers = await _http_store(db_session, "cash-close-late@test.com")
    session_id = await _http_open(client, headers)
    closed = await _post_close(client, headers, session_id, _close_payload("10000"))
    assert closed.status_code == 200, closed.text

    # Le contexte tenant (SET LOCAL) du dernier appel HTTP reste actif sur db_session.
    await SaleService(db_session).create_sale(store_id, _sale(UUID(session_id), "3000"), user_id)

    summary = (await _expected_amount(client, headers, session_id))["summary"]
    assert Decimal(summary["expected_amount"]) == Decimal("10000")
    assert Decimal(summary["late_impact"]) == Decimal("3000")


@pytest.mark.asyncio
async def test_close_concurrent_with_sale_insert_counts_it_or_reports_it_late(
    db_engine: Any,
) -> None:
    """La vente est soit dans le montant figé, soit dans l'impact après clôture, jamais perdue."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_maker() as setup:
        user_id, store_id = await _store(setup, "cash-close-race@test.com")
        await setup.commit()

    async def tenant(db: AsyncSession) -> None:
        await db.execute(text("SET LOCAL ROLE pos_app"))
        await db.execute(
            text("SELECT set_config('app.current_store_id', :sid, true)"), {"sid": str(store_id)}
        )

    for _ in range(3):
        async with session_maker() as setup:
            await tenant(setup)
            session = await _open_session(setup, store_id, user_id)
            await setup.commit()

        async def close(session_id: UUID = session.id) -> None:
            payload = CashSessionClose.model_validate(_close_payload("10000", note="Comptage"))
            async with session_maker() as db:
                await tenant(db)
                await CashSessionService(db).close(store_id, user_id, session_id, payload)
                await db.commit()

        async def sell(session_id: UUID = session.id) -> None:
            async with session_maker() as db:
                await tenant(db)
                await SaleService(db).create_sale(store_id, _sale(session_id, "3000"), user_id)
                await db.commit()

        await asyncio.gather(close(), sell())

        async with session_maker() as check:
            await tenant(check)
            detail = await CashSessionService(check).get_detail(session.id)
        assert detail.session.status == "closed"
        assert detail.summary.expected_amount + detail.summary.late_impact == Decimal("13000")
        assert detail.summary.expected_amount in (Decimal("10000"), Decimal("13000"))
        assert detail.session.discrepancy_amount == (
            Decimal("10000") - detail.summary.expected_amount
        )


@pytest.mark.asyncio
async def test_close_session_of_another_store_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers_a = await _http_store(db_session, "cash-close-rls-a@test.com")
    _, _, headers_b = await _http_store(db_session, "cash-close-rls-b@test.com")
    session_a = await _http_open(client, headers_a)

    response = await _post_close(client, headers_b, session_a, _close_payload("10000"))
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "NOT_FOUND"
    unknown = await _post_close(client, headers_a, str(uuid4()), _close_payload("10000"))
    assert unknown.status_code == 404

    detail = await _expected_amount(client, headers_a, session_a)
    assert detail["session"]["status"] == "open"


@pytest.mark.asyncio
async def test_close_payload_validation(client: AsyncClient, db_session: AsyncSession) -> None:
    _, _, headers = await _http_store(db_session, "cash-close-422@test.com")
    session_id = await _http_open(client, headers)
    without_client_expected = _close_payload("10000")
    del without_client_expected["client_expected_amount"]

    invalid = [
        (_close_payload("-1", client_expected="10000"), "counted_amount"),
        (without_client_expected, "client_expected_amount"),
        (_close_payload(closed_at=datetime.now(UTC) + timedelta(minutes=10)), "closed_at"),
        # Session ouverte il y a quelques instants : clôture la veille impossible.
        (_close_payload(closed_at=datetime.now(UTC) - timedelta(days=1)), "closed_at"),
    ]
    for payload, field in invalid:
        response = await _post_close(client, headers, session_id, payload)
        assert response.status_code == 422, (payload, response.text)
        assert response.json()["code"] == "VALIDATION_ERROR"
        assert response.json()["field"] == field

    detail = await _expected_amount(client, headers, session_id)
    assert detail["session"]["status"] == "open"


@pytest.mark.asyncio
async def test_lock_refreshes_session_already_in_identity_map(db_session: AsyncSession) -> None:
    """get_for_update relit la ligne sous le verrou, même si l'objet est déjà en mémoire."""
    user_id, store_id = await _tenant(db_session, "cash-lock-refresh@test.com")
    session = await _open_session(db_session, store_id, user_id)
    repo = CashSessionRepository(db_session)
    stale = await repo.get_by_id(session.id)
    assert stale is not None
    assert stale.status == "open"

    await _close_session(db_session, session.id)
    locked = await repo.get_for_update(session.id)

    assert locked is stale
    assert locked.status == "closed"
