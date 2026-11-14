"""Tests de la billetterie de caisse (ADR-0016)."""

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_register.schemas import DENOMINATIONS
from tests.test_cash_register import (
    _CASH_URL,
    _close_payload,
    _close_session,
    _http_store,
    _insert_open_session,
    _open_payload,
    _post_close,
    _store,
)

# 2 x 10 000 + 1 x 5 000 = 25 000 en billets ; 1 x 500 + 4 x 250 = 1 500 en pièces.
_OPENING_COUNT = [
    {"denomination_type": "bill", "denomination": 10000, "quantity": 2},
    {"denomination_type": "bill", "denomination": 5000, "quantity": 1},
    {"denomination_type": "bill", "denomination": 1000, "quantity": 0},
    {"denomination_type": "coin", "denomination": 500, "quantity": 1},
    {"denomination_type": "coin", "denomination": 250, "quantity": 4},
]
_OPENING_TOTAL = "26500"


def _line(type_: str, value: int, qty: int) -> dict[str, Any]:
    return {"denomination_type": type_, "denomination": value, "quantity": qty}


async def _open_with_count(
    client: AsyncClient,
    headers: dict[str, str],
    count: list[dict[str, Any]] | None = None,
    amount: str = _OPENING_TOTAL,
) -> tuple[dict[str, Any], Any]:
    payload = {**_open_payload(amount=amount), "opening_count": count or _OPENING_COUNT}
    return payload, await client.post(_CASH_URL, json=payload, headers=headers)


async def _detail(client: AsyncClient, headers: dict[str, str], session_id: str) -> Any:
    response = await client.get(f"{_CASH_URL}/{session_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Ouverture
# ---------------------------------------------------------------------------


async def test_open_with_count_stores_lines_and_totals(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-open@test.com")
    payload, response = await _open_with_count(client, headers)
    assert response.status_code == 201, response.text

    body = await _detail(client, headers, payload["id"])
    count = body["opening_count"]
    assert Decimal(count["bills_total"]) == Decimal("25000")
    assert Decimal(count["coins_total"]) == Decimal("1500")
    assert Decimal(count["total"]) == Decimal(_OPENING_TOTAL)
    assert isinstance(count["total"], str)
    # Billets puis pièces, coupure décroissante ; quantité nulle conservée.
    assert [
        (ln["denomination_type"], Decimal(ln["denomination"]), ln["quantity"])
        for ln in count["lines"]
    ] == [
        ("bill", Decimal("10000"), 2),
        ("bill", Decimal("5000"), 1),
        ("bill", Decimal("1000"), 0),
        ("coin", Decimal("500"), 1),
        ("coin", Decimal("250"), 4),
    ]
    assert Decimal(count["lines"][0]["subtotal"]) == Decimal("20000")
    assert Decimal(count["lines"][2]["subtotal"]) == Decimal("0")
    assert body["closing_count"] is None


async def test_open_without_count_still_accepted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Mode « Total seulement » et anciennes versions de l'app."""
    _, _, headers = await _http_store(db_session, "count-total-only@test.com")
    payload = _open_payload(amount="12000")
    assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 201

    body = await _detail(client, headers, payload["id"])
    assert body["opening_count"] is None


async def test_open_count_total_mismatch_is_422_and_writes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-mismatch@test.com")
    payload, response = await _open_with_count(client, headers, amount="30000")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["field"] == "opening_count"
    assert (await client.get(f"{_CASH_URL}/{payload['id']}", headers=headers)).status_code == 404


@pytest.mark.parametrize(
    "line",
    [
        _line("bill", 250, 1),  # coupure inconnue pour un billet
        _line("coin", 1000, 1),  # coupure inconnue pour une pièce
        _line("bill", 10000, -1),  # quantité négative
        {"denomination_type": "bill", "denomination": 10000, "quantity": 1.5},  # décimale
        {"denomination_type": "bill", "denomination": 10000, "quantity": "1"},  # texte
        _line("note", 10000, 1),  # type inconnu
        _line("bill", 10000, 100_001),  # quantité absurde
    ],
)
async def test_invalid_count_line_is_422(
    client: AsyncClient, db_session: AsyncSession, line: dict[str, Any]
) -> None:
    _, _, headers = await _http_store(db_session, f"count-invalid-{uuid4().hex[:8]}@test.com")
    payload = {**_open_payload(amount="10000"), "opening_count": [line]}

    response = await client.post(_CASH_URL, json=payload, headers=headers)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION_ERROR"


async def test_duplicate_denomination_and_empty_count_are_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-dup@test.com")
    duplicate = [_line("bill", 5000, 1), _line("bill", 5000, 1)]
    _, response = await _open_with_count(client, headers, count=duplicate, amount="10000")
    assert response.status_code == 422
    assert response.json()["field"] == "opening_count"

    payload = {**_open_payload(amount="0"), "opening_count": []}
    assert (await client.post(_CASH_URL, json=payload, headers=headers)).status_code == 422


async def test_same_denomination_as_bill_and_coin_is_allowed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """500 existe en billet et en pièce : deux lignes distinctes."""
    _, _, headers = await _http_store(db_session, "count-500@test.com")
    count = [_line("bill", 500, 2), _line("coin", 500, 3)]
    _, response = await _open_with_count(client, headers, count=count, amount="2500")
    assert response.status_code == 201, response.text


async def test_open_retry_with_same_count_is_200_and_different_count_is_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-retry@test.com")
    payload, response = await _open_with_count(client, headers)
    assert response.status_code == 201

    retry = await client.post(_CASH_URL, json=payload, headers=headers)
    assert retry.status_code == 200, retry.text

    # Même total, répartition différente : ce n'est pas le même comptage.
    other = [_line("bill", 10000, 2), _line("bill", 2000, 3), _line("coin", 500, 1)]
    conflict = await client.post(
        _CASH_URL, json={**payload, "opening_count": other}, headers=headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"

    without = {k: v for k, v in payload.items() if k != "opening_count"}
    assert (await client.post(_CASH_URL, json=without, headers=headers)).status_code == 409

    lines = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM cash_count_lines WHERE session_id = :id"),
            {"id": payload["id"]},
        )
    ).scalar()
    assert lines == len(_OPENING_COUNT)


# ---------------------------------------------------------------------------
# Clôture
# ---------------------------------------------------------------------------


async def test_close_with_count_records_lines_and_discrepancy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-close@test.com")
    payload, _ = await _open_with_count(client, headers)
    closing = [_line("bill", 10000, 2), _line("bill", 5000, 1), _line("coin", 100, 5)]
    close = {
        **_close_payload("25500", client_expected=_OPENING_TOTAL, note="Manque 1 000"),
        "closing_count": closing,
    }

    response = await _post_close(client, headers, payload["id"], close)

    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["session"]["expected_amount"]) == Decimal(_OPENING_TOTAL)
    assert Decimal(body["session"]["discrepancy_amount"]) == Decimal("-1000")
    assert Decimal(body["closing_count"]["bills_total"]) == Decimal("25000")
    assert Decimal(body["closing_count"]["coins_total"]) == Decimal("500")
    assert Decimal(body["closing_count"]["total"]) == Decimal("25500")
    assert Decimal(body["opening_count"]["total"]) == Decimal(_OPENING_TOTAL)

    # Retry identique : 200, pas de doublon.
    retry = await _post_close(client, headers, payload["id"], close)
    assert retry.status_code == 200, retry.text
    assert retry.json()["closing_count"] == body["closing_count"]

    # Même montant et même date, autre répartition : refusé.
    other = {**close, "closing_count": [_line("bill", 5000, 5), _line("coin", 500, 1)]}
    conflict = await _post_close(client, headers, payload["id"], other)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CASH_SESSION_CLOSED"


async def test_close_count_mismatch_is_422_and_session_stays_open(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _http_store(db_session, "count-close-mismatch@test.com")
    payload, _ = await _open_with_count(client, headers)
    close = {**_close_payload(_OPENING_TOTAL), "closing_count": [_line("bill", 10000, 1)]}

    response = await _post_close(client, headers, payload["id"], close)

    assert response.status_code == 422
    assert response.json()["field"] == "closing_count"
    body = await _detail(client, headers, payload["id"])
    assert body["session"]["status"] == "open"
    assert body["closing_count"] is None


async def test_close_refused_for_missing_note_writes_no_count_lines(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Atomicité : une clôture refusée par le service n'écrit aucune ligne."""
    _, _, headers = await _http_store(db_session, "count-close-atomic@test.com")
    payload, _ = await _open_with_count(client, headers)
    close = {**_close_payload("20000"), "closing_count": [_line("bill", 10000, 2)]}

    response = await _post_close(client, headers, payload["id"], close)

    assert response.status_code == 422
    assert response.json()["field"] == "closing_note"
    body = await _detail(client, headers, payload["id"])
    assert body["closing_count"] is None
    assert body["session"]["status"] == "open"


# ---------------------------------------------------------------------------
# Contraintes de base de données
# ---------------------------------------------------------------------------


async def _insert_line(
    db: AsyncSession,
    store_id: UUID,
    session_id: UUID,
    *,
    operation: str = "opening",
    quantity: int = 1,
    subtotal: int = 10000,
) -> None:
    await db.execute(
        text(
            "INSERT INTO cash_count_lines (id, store_id, session_id, operation, "
            "denomination_type, denomination, quantity, subtotal) "
            "VALUES (:id, :store_id, :session_id, :operation, 'bill', 10000, :q, :s)"
        ),
        {
            "id": uuid4(),
            "store_id": store_id,
            "session_id": session_id,
            "operation": operation,
            "q": quantity,
            "s": subtotal,
        },
    )


async def test_count_lines_are_immutable(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "count-immutable@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _insert_line(db_session, store_id, session_id)

    for statement in (
        "UPDATE cash_count_lines SET quantity = 2, subtotal = 20000",
        "DELETE FROM cash_count_lines",
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            async with db_session.begin_nested():
                await db_session.execute(text(statement))


async def test_subtotal_must_match_quantity(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "count-subtotal@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())

    with pytest.raises(DBAPIError, match="chk_cash_count_lines_subtotal"):
        async with db_session.begin_nested():
            await _insert_line(db_session, store_id, session_id, quantity=2, subtotal=10000)


async def test_no_count_line_on_closed_session(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "count-closed@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _close_session(db_session, session_id)

    with pytest.raises(DBAPIError, match="is closed"):
        async with db_session.begin_nested():
            await _insert_line(db_session, store_id, session_id, operation="closing")


async def test_count_lines_are_isolated_by_store(db_session: AsyncSession) -> None:
    _, store_a = await _store(db_session, "count-rls-a@test.com")
    _, store_b = await _store(db_session, "count-rls-b@test.com")
    session_a = await _insert_open_session(db_session, store_a, uuid4())
    await _insert_line(db_session, store_a, session_a)
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_b}'"))
    lines = (await db_session.execute(text("SELECT COUNT(*) FROM cash_count_lines"))).scalar()
    assert lines == 0

    # Insertion pour une autre boutique refusée par la politique RLS.
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await _insert_line(db_session, store_a, session_a, operation="closing")


async def test_purge_store_removes_count_lines(db_session: AsyncSession) -> None:
    _, store_id = await _store(db_session, "count-purge@test.com")
    session_id = await _insert_open_session(db_session, store_id, uuid4())
    await _insert_line(db_session, store_id, session_id)
    await _insert_line(db_session, store_id, session_id, operation="closing")
    await _close_session(db_session, session_id)
    await db_session.flush()

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))
    await db_session.execute(text("SELECT purge_store(:id)"), {"id": store_id})

    lines = (await db_session.execute(text("SELECT COUNT(*) FROM cash_count_lines"))).scalar()
    assert lines == 0


def test_denominations_match_flutter_list() -> None:
    """Cohérence Flutter/backend : même gamme que `fcfaDenominations`
    (lib/features/cash_register/domain/entities/denomination.dart, côté app)."""
    assert DENOMINATIONS == {
        "bill": (10000, 5000, 2000, 1000, 500),
        "coin": (500, 250, 200, 100, 50, 25, 10, 5),
    }
