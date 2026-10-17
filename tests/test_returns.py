"""Tests des retours clients (ADR-0010).

Couvre le calcul du montant remboursable, l'endpoint POST /api/v1/sync/returns
(retours partiels et successifs, refus, idempotence, stock), le pull, la
concurrence entre deux appareils, l'immuabilité et l'isolation RLS.
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.returns.exceptions import ReturnRejectedError, ReturnRejectionCode
from app.modules.returns.refund import allocate_paid_amounts, refund_for
from app.modules.returns.schemas import SaleReturnCreate
from app.modules.returns.service import ReturnService
from app.modules.sales.schemas import SaleCreate
from app.modules.sales.service import SaleService
from tests.test_sync import _create_product, _create_store, _create_user, _headers

# ---------------------------------------------------------------------------
# Calcul du remboursement (fonctions pures)
# ---------------------------------------------------------------------------

_A, _B, _C = (UUID(int=1), UUID(int=2), UUID(int=3))


def test_paid_amounts_without_global_discount_are_line_totals() -> None:
    paid = allocate_paid_amounts([(_A, Decimal("3000")), (_B, Decimal("2500"))], Decimal("5500"))
    assert paid == {_A: 3000, _B: 2500}


def test_global_discount_is_split_pro_rata_and_sums_to_total() -> None:
    # 1000 / 1000 / 1000, remise 100 → 966,67 chacun : 967 + 967 + 966 = 2900.
    lines = [(_A, Decimal("1000")), (_B, Decimal("1000")), (_C, Decimal("1000"))]
    paid = allocate_paid_amounts(lines, Decimal("2900"))
    assert sum(paid.values()) == 2900
    # Égalité de reste : départagée par l'id croissant.
    assert paid == {_A: 967, _B: 967, _C: 966}


def test_global_discount_follows_line_weight() -> None:
    paid = allocate_paid_amounts([(_A, Decimal("3000")), (_B, Decimal("1000"))], Decimal("3600"))
    assert paid == {_A: 2700, _B: 900}


def test_free_sale_refunds_nothing() -> None:
    assert allocate_paid_amounts([(_A, Decimal("0"))], Decimal("0")) == {_A: 0}


def test_successive_partial_refunds_sum_to_paid_amount() -> None:
    # 5 unités payées 1001 F au total : 2 puis 3.
    first = refund_for(1001, 5, 0, 2)
    second = refund_for(1001, 5, 2, 3)
    assert (first, second) == (400, 601)
    assert first + second == 1001


def test_refund_never_exceeds_paid_one_unit_at_a_time() -> None:
    refunds = [refund_for(1000, 3, already, 1) for already in range(3)]
    assert refunds == [333, 333, 334]
    assert sum(refunds) == 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sale_payload(lines: list[dict[str, Any]], discount: Decimal | None = None) -> dict[str, Any]:
    """Vente avec des lignes `{id, product_id, price, quantity, discount}`."""
    items = []
    for line in lines:
        gross = Decimal(line["price"]) * line["quantity"]
        line_discount = Decimal(line.get("discount", "0"))
        items.append(
            {
                "id": str(line["id"]),
                "product_id": str(line["product_id"]) if line.get("product_id") else None,
                "product_name_at_sale": line.get("name", "Article"),
                "unit_price_at_sale": str(line["price"]),
                "quantity": line["quantity"],
                "line_total": str(gross - line_discount),
                "discount_type": "amount" if line_discount else None,
                "discount_value": str(line_discount) if line_discount else None,
                "discount_amount": str(line_discount),
            }
        )
    subtotal = sum((Decimal(i["line_total"]) for i in items), Decimal("0"))
    sale_discount = discount or Decimal("0")
    return {
        "id": str(uuid4()),
        "items": items,
        "total_amount": str(subtotal - sale_discount),
        "vat_amount": "0",
        "payment_method": "cash",
        "created_at": datetime.now(UTC).isoformat(),
        "discount_type": "amount" if discount else None,
        "discount_value": str(discount) if discount else None,
        "discount_amount": str(sale_discount),
    }


def _return_payload(
    sale_id: str,
    lines: list[tuple[UUID, int, str, str]],
    *,
    reason: str = "defective",
    note: str | None = None,
    return_id: UUID | None = None,
) -> dict[str, Any]:
    """Retour avec des lignes `(sale_item_id, quantité, état, montant)`."""
    items = [
        {
            "id": str(uuid4()),
            "sale_item_id": str(item_id),
            "quantity": quantity,
            "condition": condition,
            "refund_amount": amount,
        }
        for item_id, quantity, condition, amount in lines
    ]
    return {
        "id": str(return_id or uuid4()),
        "sale_id": sale_id,
        "reason": reason,
        "note": note,
        "refund_method": "cash",
        "refund_amount": str(sum(Decimal(i["refund_amount"]) for i in items)),
        "created_at": datetime.now(UTC).isoformat(),
        "items": items,
    }


async def _push_sale(client: AsyncClient, headers: dict[str, str], sale: dict[str, Any]) -> None:
    response = await client.post("/api/v1/sync/sales", json={"sales": [sale]}, headers=headers)
    assert response.json()["results"][0]["status"] == "created"


async def _push_return(
    client: AsyncClient, headers: dict[str, str], payload: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/sync/returns", json={"returns": [payload]}, headers=headers
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()["results"][0]
    return result


async def _setup(db: AsyncSession, email: str, stock: int | None = 10) -> tuple[Any, Any, Any]:
    user = await _create_user(db, email)
    store = await _create_store(db, user.id)
    product = await _create_product(db, store.id, name="Coca 33cl")
    product.current_stock = stock
    await db.commit()
    return user, store, product


async def _stock(db: AsyncSession, product_id: UUID) -> int | None:
    value: int | None = (
        await db.execute(
            text("SELECT current_stock FROM products WHERE id = :id"), {"id": str(product_id)}
        )
    ).scalar()
    return value


# ---------------------------------------------------------------------------
# Endpoint POST /api/v1/sync/returns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_return_one_item_of_multi_item_sale(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Retour d'un article revendable sur deux : remboursé, remis en stock, numéroté."""
    user, store, product = await _setup(db_session, "ret-one@test.com")
    headers = _headers(user.id, store.id)
    coca, pain = uuid4(), uuid4()
    sale = _sale_payload(
        [
            {"id": coca, "product_id": product.id, "price": "1000", "quantity": 3},
            {"id": pain, "price": "250", "quantity": 2},
        ]
    )
    await _push_sale(client, headers, sale)

    result = await _push_return(
        client, headers, _return_payload(sale["id"], [(coca, 1, "resellable", "1000")])
    )

    assert result["status"] == "created"
    assert result["return_number"] == 1
    # 10 - 3 vendus + 1 rendu revendable.
    assert await _stock(db_session, product.id) == 8
    movement = (
        await db_session.execute(
            text(
                "SELECT reason, quantity_delta, sale_return_id FROM stock_movements "
                "WHERE reason = 'customer_return'"
            )
        )
    ).one()
    assert movement.quantity_delta == 1
    assert str(movement.sale_return_id) == result["id"]


@pytest.mark.asyncio
async def test_partial_then_remaining_then_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """2 unités sur 5, puis les 3 restantes, puis une de trop : refusée."""
    user, store, product = await _setup(db_session, "ret-partial@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 5}])
    await _push_sale(client, headers, sale)

    first = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 2, "resellable", "2000")])
    )
    second = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 3, "resellable", "3000")])
    )
    third = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "0")])
    )

    assert (first["status"], second["status"]) == ("created", "created")
    assert (first["return_number"], second["return_number"]) == (1, 2)
    assert third["status"] == "rejected"
    assert third["error_code"] == "quantity_exceeded"
    assert await _stock(db_session, product.id) == 10


@pytest.mark.asyncio
async def test_line_and_global_discounts_are_refunded_as_paid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Réduction de ligne + remise globale : le remboursement total = montant encaissé."""
    user, store, product = await _setup(db_session, "ret-discount@test.com")
    headers = _headers(user.id, store.id)
    first, second = uuid4(), uuid4()
    # Lignes nettes 1800 (2 x 1000 - 200) et 1200, remise globale 300 → encaissé 2700.
    sale = _sale_payload(
        [
            {
                "id": first,
                "product_id": product.id,
                "price": "1000",
                "quantity": 2,
                "discount": "200",
            },
            {"id": second, "price": "400", "quantity": 3},
        ],
        discount=Decimal("300"),
    )
    await _push_sale(client, headers, sale)
    paid = allocate_paid_amounts(
        [(first, Decimal("1800")), (second, Decimal("1200"))], Decimal("2700")
    )
    assert paid == {first: 1620, second: 1080}

    result = await _push_return(
        client,
        headers,
        _return_payload(
            sale["id"], [(first, 2, "resellable", "1620"), (second, 3, "damaged", "1080")]
        ),
    )

    assert result["status"] == "created"
    total = (
        await db_session.execute(
            text("SELECT refund_amount FROM sale_returns WHERE id = :id"), {"id": result["id"]}
        )
    ).scalar()
    assert total == Decimal("2700")


@pytest.mark.asyncio
async def test_amount_other_than_paid_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un montant supérieur au payé (prix catalogue actuel) est refusé."""
    user, store, product = await _setup(db_session, "ret-amount@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 1}])
    await _push_sale(client, headers, sale)
    # Le produit coûte désormais 1500 : le retour reste remboursé 1000.
    product.selling_price = Decimal("1500")
    await db_session.commit()

    refused = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "1500")])
    )
    accepted = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "1000")])
    )

    assert refused["status"] == "rejected"
    assert refused["error_code"] == "amount_mismatch"
    assert accepted["status"] == "created"


@pytest.mark.asyncio
async def test_unsellable_item_is_not_restocked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Article non revendable : tracé, sans retour dans le stock disponible."""
    user, store, product = await _setup(db_session, "ret-unsellable@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 2}])
    await _push_sale(client, headers, sale)

    result = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 2, "unsellable", "2000")])
    )

    assert result["status"] == "created"
    assert await _stock(db_session, product.id) == 8
    restocked = (
        await db_session.execute(text("SELECT restocked, condition FROM sale_return_items"))
    ).one()
    assert (restocked.restocked, restocked.condition) == (False, "unsellable")
    movements = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM stock_movements WHERE reason = 'customer_return'")
        )
    ).scalar()
    assert movements == 0


@pytest.mark.asyncio
async def test_untracked_product_stays_untracked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Produit au stock non suivi : le retour revendable ne crée pas de stock."""
    user, store, product = await _setup(db_session, "ret-untracked@test.com", stock=None)
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "500", "quantity": 1}])
    await _push_sale(client, headers, sale)

    result = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "500")])
    )

    assert result["status"] == "created"
    assert await _stock(db_session, product.id) is None


@pytest.mark.asyncio
async def test_same_return_sent_twice_is_idempotent(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Nouvel envoi du même retour (timeout réseau) : already_exists, aucun doublon."""
    user, store, product = await _setup(db_session, "ret-idem@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 2}])
    await _push_sale(client, headers, sale)
    payload = _return_payload(sale["id"], [(line, 1, "resellable", "1000")])

    first = await _push_return(client, headers, payload)
    second = await _push_return(client, headers, payload)

    assert first["status"] == "created"
    assert second["status"] == "already_exists"
    assert second["return_number"] == first["return_number"]
    count = (await db_session.execute(text("SELECT COUNT(*) FROM sale_returns"))).scalar()
    assert count == 1
    assert await _stock(db_session, product.id) == 9


@pytest.mark.asyncio
async def test_unknown_sale_and_foreign_item_are_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store, product = await _setup(db_session, "ret-unknown@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 1}])
    await _push_sale(client, headers, sale)

    no_sale = await _push_return(
        client, headers, _return_payload(str(uuid4()), [(line, 1, "resellable", "1000")])
    )
    foreign = await _push_return(
        client, headers, _return_payload(sale["id"], [(uuid4(), 1, "resellable", "1000")])
    )

    assert no_sale["error_code"] == "sale_not_found"
    assert foreign["error_code"] == "item_not_in_sale"


@pytest.mark.asyncio
async def test_reason_other_requires_note(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store, _ = await _setup(db_session, "ret-note@test.com")
    payload = _return_payload(str(uuid4()), [(uuid4(), 1, "resellable", "0")], reason="other")

    response = await client.post(
        "/api/v1/sync/returns", json={"returns": [payload]}, headers=_headers(user.id, store.id)
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pull_includes_returns_after_their_sale(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store, product = await _setup(db_session, "ret-pull@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 2}])
    await _push_sale(client, headers, sale)
    result = await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "damaged", "1000")])
    )

    response = await client.get("/api/v1/sync/changes", headers=headers)

    data = response.json()
    assert [s["id"] for s in data["sales"]] == [sale["id"]]
    returned = data["returns"]
    assert [r["id"] for r in returned] == [result["id"]]
    assert returned[0]["items"][0]["sale_item_id"] == str(line)
    assert returned[0]["items"][0]["restocked"] is False


# ---------------------------------------------------------------------------
# Concurrence, immuabilité, RLS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_returns_cannot_exceed_sold_quantity(db_engine: Any) -> None:
    """Deux appareils retournent 3 unités sur 5 en même temps : le second est refusé."""
    session_maker = async_sessionmaker(db_engine, expire_on_commit=False)
    line = uuid4()
    async with session_maker() as setup:
        user, store, product = await _setup(setup, "ret-concurrent@test.com")
        sale = SaleCreate.model_validate(
            _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 5}])
        )
        await SaleService(setup).create_sale(store.id, sale, user.id)
        await setup.commit()

    def payload() -> SaleReturnCreate:
        return SaleReturnCreate.model_validate(
            _return_payload(str(sale.id), [(line, 3, "resellable", "3000")])
        )

    async with session_maker() as first, session_maker() as second:
        await ReturnService(first).create_return(store.id, payload(), user.id)
        # Le second attend le verrou de la vente tenu par le premier.
        pending = asyncio.create_task(
            ReturnService(second).create_return(store.id, payload(), user.id)
        )
        await asyncio.sleep(0.3)
        assert not pending.done()

        await first.commit()
        with pytest.raises(ReturnRejectedError) as rejected:
            await pending
        await second.rollback()

    assert rejected.value.code == ReturnRejectionCode.quantity_exceeded


@pytest.mark.asyncio
async def test_returns_are_immutable(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store, product = await _setup(db_session, "ret-immutable@test.com")
    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 1}])
    await _push_sale(client, headers, sale)
    await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "1000")])
    )
    await db_session.execute(text("RESET ROLE"))

    with pytest.raises(DBAPIError, match="immutable"):
        async with db_session.begin_nested():
            await db_session.execute(text("UPDATE sale_returns SET refund_amount = 0"))
    with pytest.raises(DBAPIError, match="immutable"):
        async with db_session.begin_nested():
            await db_session.execute(text("DELETE FROM sale_return_items"))


@pytest.mark.asyncio
async def test_store_cannot_read_returns_of_another_store(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Isolation RLS : la boutique B ne voit ni les retours ni les lignes de A."""
    user_a, store_a, product = await _setup(db_session, "ret-rls-a@test.com")
    user_b = await _create_user(db_session, "ret-rls-b@test.com")
    store_b = await _create_store(db_session, user_b.id)
    await db_session.commit()
    line = uuid4()
    headers_a = _headers(user_a.id, store_a.id)
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 1}])
    await _push_sale(client, headers_a, sale)
    await _push_return(
        client, headers_a, _return_payload(sale["id"], [(line, 1, "resellable", "1000")])
    )

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_b.id}'"))
    returns = (await db_session.execute(text("SELECT COUNT(*) FROM sale_returns"))).scalar()
    items = (await db_session.execute(text("SELECT COUNT(*) FROM sale_return_items"))).scalar()

    assert (returns, items) == (0, 0)
    response = await client.get("/api/v1/sync/changes", headers=_headers(user_b.id, store_b.id))
    assert response.json()["returns"] == []
