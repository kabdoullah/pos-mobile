"""Tests d'intégration du module sales."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.sales.models import Sale
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(email=email, password_hash=_DUMMY_HASH, phone_number="+225 01 02 03 04 05")
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def _create_store(db: AsyncSession, owner_id: UUID, name: str = "Ma boutique") -> Store:
    store = Store(owner_id=owner_id, name=name)
    db.add(store)
    await db.flush()
    await db.refresh(store)
    return store


async def _create_product(
    db: AsyncSession,
    store_id: UUID,
    name: str = "Produit test",
    unit_price: Decimal = Decimal("1000.00"),
) -> Product:
    product = Product(store_id=store_id, name=name, unit_price=unit_price)
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


def _headers(user_id: UUID, store_id: UUID) -> dict[str, str]:
    token = create_access_token(user_id, store_id)
    return {"Authorization": f"Bearer {token}"}


def _sale_payload(
    *,
    sale_id: UUID | None = None,
    product_id: UUID | None = None,
    product_name: str = "Baguette",
    unit_price: str = "1000.00",
    quantity: int = 5,
    line_total: str = "5000.00",
    total_amount: str = "5000.00",
    vat_amount: str = "0.00",
    payment_method: str = "cash",
    cash_amount: str | None = None,
    mobile_money_amount: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Construit un payload de vente valide (cash, 1 item, 5000 FCFA par défaut)."""
    if sale_id is None:
        sale_id = uuid4()
    if created_at is None:
        created_at = datetime.now(UTC).isoformat()
    return {
        "id": str(sale_id),
        "items": [
            {
                "product_id": str(product_id) if product_id is not None else None,
                "product_name_at_sale": product_name,
                "unit_price_at_sale": unit_price,
                "quantity": quantity,
                "line_total": line_total,
            }
        ],
        "total_amount": total_amount,
        "vat_amount": vat_amount,
        "payment_method": payment_method,
        "cash_amount": cash_amount,
        "mobile_money_amount": mobile_money_amount,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# POST /api/v1/sales — Création
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sale_success_cash(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST payload cash valide → 201, champs présents."""
    user = await _create_user(db_session, "sale-cash@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["store_id"] == str(store.id)
    assert data["total_amount"] == "5000.00"
    assert data["payment_method"] == "cash"
    assert data["receipt_number"] is not None
    assert len(data["items"]) == 1
    assert data["items"][0]["product_name_at_sale"] == "Baguette"


@pytest.mark.asyncio
async def test_create_sale_success_mobile_money(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST avec payment_method mobile_money_orange → 201."""
    user = await _create_user(db_session, "sale-mobile@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(payment_method="mobile_money_orange"),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    assert response.json()["payment_method"] == "mobile_money_orange"


@pytest.mark.asyncio
async def test_create_sale_success_mixed(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST mixed avec cash+mobile_money qui somment au total → 201."""
    user = await _create_user(db_session, "sale-mixed@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(
            payment_method="mixed",
            cash_amount="3000.00",
            mobile_money_amount="2000.00",
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["payment_method"] == "mixed"
    assert data["cash_amount"] == "3000.00"
    assert data["mobile_money_amount"] == "2000.00"


@pytest.mark.asyncio
async def test_create_sale_mixed_amounts_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """mixed mais cash + mobile_money ≠ total → 422."""
    user = await _create_user(db_session, "sale-mixed-inv@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(
            payment_method="mixed",
            cash_amount="2000.00",
            mobile_money_amount="2000.00",  # 4000 != 5000
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_total_doesnt_match_items(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """total_amount != sum(line_totals) → 422."""
    user = await _create_user(db_session, "sale-total-mismatch@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(total_amount="9999.00"),  # items sum = 5000
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_line_total_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """line_total != unit_price * quantity → 422."""
    user = await _create_user(db_session, "sale-line-inv@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    payload = _sale_payload()
    payload["items"][0]["line_total"] = "4000.00"  # 1000 * 5 = 5000, pas 4000
    payload["total_amount"] = "4000.00"  # match le total pour isoler l'erreur item

    response = await client.post(
        "/api/v1/sales",
        json=payload,
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_negative_amount(client: AsyncClient, db_session: AsyncSession) -> None:
    """total_amount négatif → 422."""
    user = await _create_user(db_session, "sale-neg@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    payload = _sale_payload()
    payload["total_amount"] = "-100.00"

    response = await client.post(
        "/api/v1/sales",
        json=payload,
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_empty_items(client: AsyncClient, db_session: AsyncSession) -> None:
    """items vide → 422 (min_length=1)."""
    user = await _create_user(db_session, "sale-empty@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    payload = _sale_payload()
    payload["items"] = []

    response = await client.post(
        "/api/v1/sales",
        json=payload,
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_future_created_at(client: AsyncClient, db_session: AsyncSession) -> None:
    """created_at dans le futur (>5 min) → 422."""
    user = await _create_user(db_session, "sale-future@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(created_at=future),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_sale_vat_greater_than_total(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """vat_amount > total_amount → 422."""
    user = await _create_user(db_session, "sale-vat@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(vat_amount="9999.00"),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Idempotence (CRITIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sale_idempotent_same_payload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Poster le même payload deux fois → les deux retournent 201 avec la même vente."""
    user = await _create_user(db_session, "idem-same@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    payload = _sale_payload()
    headers = _headers(user.id, store.id)

    r1 = await client.post("/api/v1/sales", json=payload, headers=headers)
    r2 = await client.post("/api/v1/sales", json=payload, headers=headers)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["receipt_number"] == r2.json()["receipt_number"]

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM sales WHERE store_id = :sid"),
        {"sid": str(store.id)},
    )
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_create_sale_idempotent_with_timeout_simulation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Re-poster le même id avec payload différent → retourne la vente originale."""
    user = await _create_user(db_session, "idem-timeout@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    sale_id = uuid4()
    headers = _headers(user.id, store.id)

    payload_1 = _sale_payload(sale_id=sale_id, total_amount="5000.00")
    r1 = await client.post("/api/v1/sales", json=payload_1, headers=headers)
    assert r1.status_code == 201

    # Même id, payload avec un total différent (simule un retry après timeout)
    payload_2 = _sale_payload(
        sale_id=sale_id,
        unit_price="2000.00",
        quantity=4,
        line_total="8000.00",
        total_amount="8000.00",
    )
    r2 = await client.post("/api/v1/sales", json=payload_2, headers=headers)
    assert r2.status_code == 201
    assert r2.json()["total_amount"] == "5000.00"  # montant original, pas 8000


@pytest.mark.asyncio
async def test_receipt_number_generated_atomically(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """3 ventes consécutives → receipt_numbers séquentiels."""
    user = await _create_user(db_session, "receipt-seq@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    receipts = []
    for _ in range(3):
        r = await client.post("/api/v1/sales", json=_sale_payload(), headers=headers)
        assert r.status_code == 201
        receipts.append(r.json()["receipt_number"])

    assert receipts[1] == receipts[0] + 1
    assert receipts[2] == receipts[1] + 1


# ---------------------------------------------------------------------------
# Immuabilité (CRITIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_patch_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH /api/v1/sales/{id} → 405 Method Not Allowed."""
    user = await _create_user(db_session, "immut-patch@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    r = await client.post("/api/v1/sales", json=_sale_payload(), headers=headers)
    sale_id = r.json()["id"]

    response = await client.patch(
        f"/api/v1/sales/{sale_id}",
        json={"total_amount": "9999.00"},
        headers=headers,
    )
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_no_delete_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    """DELETE /api/v1/sales/{id} → 405 Method Not Allowed."""
    user = await _create_user(db_session, "immut-delete@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    r = await client.post("/api/v1/sales", json=_sale_payload(), headers=headers)
    sale_id = r.json()["id"]

    response = await client.delete(f"/api/v1/sales/{sale_id}", headers=headers)
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_direct_db_update_blocked(client: AsyncClient, db_session: AsyncSession) -> None:
    """UPDATE direct via SQL → exception du trigger d'immuabilité PostgreSQL."""
    user = await _create_user(db_session, "immut-sql@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    r = await client.post("/api/v1/sales", json=_sale_payload(), headers=headers)
    assert r.status_code == 201
    sale_id = r.json()["id"]

    with pytest.raises(DBAPIError):
        await db_session.execute(
            text("UPDATE sales SET total_amount = 9999 WHERE id = :id"),
            {"id": sale_id},
        )


# ---------------------------------------------------------------------------
# product_id NULL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_sale_with_deleted_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Produit soft-deleted → sale créée, sale_item.product_id=NULL, snapshot conservé."""
    user = await _create_user(db_session, "sale-del-prod@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Baguette")
    await db_session.commit()

    # Soft-delete du produit
    product.deleted_at = datetime.now(UTC)
    await db_session.flush()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(product_id=product.id, product_name="Baguette"),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["product_id"] is None
    assert item["product_name_at_sale"] == "Baguette"
    assert item["unit_price_at_sale"] == "1000.00"


@pytest.mark.asyncio
async def test_create_sale_with_unknown_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """product_id inexistant côté serveur → sale créée avec product_id=NULL."""
    user = await _create_user(db_session, "sale-unknown-prod@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale_payload(product_id=uuid4(), product_name="Produit fantôme"),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["product_id"] is None
    assert item["product_name_at_sale"] == "Produit fantôme"


# ---------------------------------------------------------------------------
# Listing et pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sales_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    """60 ventes + limit=20 → 20 items, has_more=True, next_cursor non nul."""
    user = await _create_user(db_session, "paginate-sales@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    base_time = datetime.now(UTC) - timedelta(days=1)
    for i in range(60):
        sale = Sale(
            id=uuid4(),
            store_id=store.id,
            total_amount=Decimal("1000.00"),
            vat_amount=Decimal("0.00"),
            payment_method="cash",
            created_at=base_time + timedelta(minutes=i),
        )
        db_session.add(sale)
    await db_session.flush()

    response = await client.get(
        "/api/v1/sales?limit=20",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 20
    assert data["has_more"] is True
    assert data["next_cursor"] is not None


@pytest.mark.asyncio
async def test_list_sales_with_date_filter(client: AsyncClient, db_session: AsyncSession) -> None:
    """Filtres date_from + date_to → seules les ventes dans la fenêtre sont retournées."""
    user = await _create_user(db_session, "date-filter@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=2)).isoformat()
    today = now.isoformat()
    headers = _headers(user.id, store.id)

    await client.post("/api/v1/sales", json=_sale_payload(created_at=yesterday), headers=headers)
    await client.post("/api/v1/sales", json=_sale_payload(created_at=today), headers=headers)

    date_from = (now - timedelta(hours=1)).isoformat()
    date_to = (now + timedelta(hours=1)).isoformat()

    response = await client.get(
        "/api/v1/sales",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Détail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_sale_by_id_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /{sale_id} → 200 avec items inclus."""
    user = await _create_user(db_session, "get-sale-ok@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    r = await client.post("/api/v1/sales", json=_sale_payload(), headers=headers)
    sale_id = r.json()["id"]

    response = await client.get(f"/api/v1/sales/{sale_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sale_id
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_sale_by_id_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET avec UUID inexistant → 404."""
    user = await _create_user(db_session, "get-sale-404@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/sales/{uuid4()}",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Résumé du jour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_today_summary_empty(client: AsyncClient, db_session: AsyncSession) -> None:
    """Aucune vente aujourd'hui → total=0, sales_count=0."""
    user = await _create_user(db_session, "summary-empty@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/sales/today/summary",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sales_count"] == 0
    assert Decimal(data["total_amount"]) == Decimal("0")
    assert data["by_payment_method"] == {}
    assert data["top_products"] == []


@pytest.mark.asyncio
async def test_today_summary_with_sales(client: AsyncClient, db_session: AsyncSession) -> None:
    """5 ventes (2 cash + 2 mobile_money_orange + 1 mixed) → résumé cohérent."""
    user = await _create_user(db_session, "summary-sales@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)

    # 2 ventes cash à 5000
    for _ in range(2):
        await client.post("/api/v1/sales", json=_sale_payload(product_name="Pain"), headers=headers)

    # 2 ventes mobile_money_orange à 1800 (unit=600, qty=3)
    for _ in range(2):
        await client.post(
            "/api/v1/sales",
            json=_sale_payload(
                unit_price="600.00",
                quantity=3,
                line_total="1800.00",
                total_amount="1800.00",
                payment_method="mobile_money_orange",
                product_name="Lait",
            ),
            headers=headers,
        )

    # 1 vente mixed à 5000 (cash=3000 + mobile=2000)
    await client.post(
        "/api/v1/sales",
        json=_sale_payload(
            payment_method="mixed",
            cash_amount="3000.00",
            mobile_money_amount="2000.00",
            product_name="Pain",
        ),
        headers=headers,
    )

    response = await client.get("/api/v1/sales/today/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # 5000*2 + 1800*2 + 5000 = 18600
    assert data["sales_count"] == 5
    assert Decimal(data["total_amount"]) == Decimal("18600.00")
    assert "cash" in data["by_payment_method"]
    assert data["by_payment_method"]["cash"]["count"] == 2
    assert "mobile_money_orange" in data["by_payment_method"]
    assert data["by_payment_method"]["mobile_money_orange"]["count"] == 2
    assert "mixed" in data["by_payment_method"]
    # Pain vendu dans 3 ventes (2 cash + 1 mixed) : 5*3=15 unités
    pain = next(p for p in data["top_products"] if p["product_name"] == "Pain")
    assert pain["quantity_sold"] == 15
    # Lait vendu dans 2 ventes : 3*2=6 unités
    lait = next(p for p in data["top_products"] if p["product_name"] == "Lait")
    assert lait["quantity_sold"] == 6


@pytest.mark.asyncio
async def test_today_summary_excludes_yesterday(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Vente datée d'hier + vente d'aujourd'hui → seule celle d'aujourd'hui dans le résumé."""
    user = await _create_user(db_session, "summary-yesterday@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    today = datetime.now(UTC).isoformat()

    await client.post("/api/v1/sales", json=_sale_payload(created_at=yesterday), headers=headers)
    await client.post("/api/v1/sales", json=_sale_payload(created_at=today), headers=headers)

    response = await client.get("/api/v1/sales/today/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sales_count"] == 1
    assert Decimal(data["total_amount"]) == Decimal("5000.00")


@pytest.mark.asyncio
async def test_today_summary_top_products_limited_to_5(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """7 produits différents vendus → top_products contient les 5 plus vendus."""
    user = await _create_user(db_session, "summary-top5@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    # Quantités décroissantes : A=100, B=90, C=80, D=70, E=60, F=50, G=40
    products = [("A", 100), ("B", 90), ("C", 80), ("D", 70), ("E", 60), ("F", 50), ("G", 40)]
    for name, qty in products:
        total = str(qty * 10)  # unit_price=10
        line = total
        await client.post(
            "/api/v1/sales",
            json=_sale_payload(
                unit_price="10.00",
                quantity=qty,
                line_total=f"{line}.00",
                total_amount=f"{total}.00",
                product_name=name,
            ),
            headers=headers,
        )

    response = await client.get("/api/v1/sales/today/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()

    top = data["top_products"]
    assert len(top) == 5
    top_names = {p["product_name"] for p in top}
    assert {"A", "B", "C", "D", "E"} == top_names
    assert "F" not in top_names
    assert "G" not in top_names


# ---------------------------------------------------------------------------
# Isolation tenant (CRITIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_a_cannot_get_sale_of_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A ne peut pas lire la vente de B → 404 (pas 200, pas 403)."""
    user_a = await _create_user(db_session, "iso-a-sale-get@test.com")
    user_b = await _create_user(db_session, "iso-b-sale-get@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    # Créer une vente pour B
    r = await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user_b.id, store_b.id),
    )
    sale_id_b = r.json()["id"]

    # A tente de lire la vente de B
    response = await client.get(
        f"/api/v1/sales/{sale_id_b}",
        headers=_headers(user_a.id, store_a.id),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_a_list_sales_excludes_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La liste de A ne contient aucune vente de B."""
    user_a = await _create_user(db_session, "iso-a-sale-list@test.com")
    user_b = await _create_user(db_session, "iso-b-sale-list@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    r_a = await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user_a.id, store_a.id),
    )
    r_b = await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user_b.id, store_b.id),
    )
    sale_id_a = r_a.json()["id"]
    sale_id_b = r_b.json()["id"]

    response = await client.get(
        "/api/v1/sales",
        headers=_headers(user_a.id, store_a.id),
    )
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert sale_id_a in ids
    assert sale_id_b not in ids


@pytest.mark.asyncio
async def test_user_a_today_summary_excludes_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Le résumé de A ne compte que les ventes de A, même si B a vendu aujourd'hui."""
    user_a = await _create_user(db_session, "iso-a-summary@test.com")
    user_b = await _create_user(db_session, "iso-b-summary@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    # A vend pour 5000
    await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user_a.id, store_a.id),
    )
    # B vend pour 5000
    await client.post(
        "/api/v1/sales",
        json=_sale_payload(),
        headers=_headers(user_b.id, store_b.id),
    )

    response = await client.get(
        "/api/v1/sales/today/summary",
        headers=_headers(user_a.id, store_a.id),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["sales_count"] == 1
    assert Decimal(data["total_amount"]) == Decimal("5000.00")
