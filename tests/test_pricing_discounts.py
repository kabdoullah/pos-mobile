"""Tests ADR-0009 : prix d'achat, prix de vente, réductions et instantané des ventes."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.bulk_import import parse_bulk_import_file
from app.modules.sales.schemas import DiscountType, discount_amount_for
from tests.test_sales import _create_product, _create_store, _create_user, _headers


def _item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "product_id": None,
        "product_name_at_sale": "Coca-Cola",
        "unit_price_at_sale": "2000.00",
        "quantity": 2,
        "line_total": "4000.00",
    }
    item.update(overrides)
    return item


def _sale(items: list[dict[str, Any]], total: str, **overrides: Any) -> dict[str, Any]:
    sale: dict[str, Any] = {
        "id": str(uuid4()),
        "items": items,
        "total_amount": total,
        "vat_amount": "0.00",
        "payment_method": "cash",
        "created_at": datetime.now(UTC).isoformat(),
    }
    sale.update(overrides)
    return sale


# ---------------------------------------------------------------------------
# Règle de calcul
# ---------------------------------------------------------------------------


def test_discount_amount_rules() -> None:
    """Montant fixe, pourcentage arrondi au franc demi-haut, plafond au brut."""
    assert discount_amount_for(DiscountType.amount, Decimal(300), Decimal(2000)) == 300
    assert discount_amount_for(DiscountType.percentage, Decimal(10), Decimal(2000)) == 200
    assert discount_amount_for(DiscountType.percentage, Decimal("12.5"), Decimal(1999)) == 250
    assert discount_amount_for(DiscountType.percentage, Decimal(10), Decimal(1995)) == 200
    assert discount_amount_for(DiscountType.percentage, Decimal(10), Decimal(1994)) == 199


# ---------------------------------------------------------------------------
# Produits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_selling_and_purchase_price(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Création avec selling_price + purchase_price ; unit_price reste exposé (déprécié)."""
    user = await _create_user(db_session, "pricing-product@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Coca", "selling_price": "2000.00", "purchase_price": "1500.00"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["selling_price"] == "2000.00"
    assert data["purchase_price"] == "1500.00"
    assert data["unit_price"] == "2000.00"


@pytest.mark.asyncio
async def test_product_negative_purchase_price_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = await _create_user(db_session, "pricing-negative@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Coca", "selling_price": "2000.00", "purchase_price": "-1.00"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_product_purchase_price_absent_keeps_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ancienne app (sans purchase_price) : le prix d'achat serveur est conservé ;
    null explicite l'efface."""
    user = await _create_user(db_session, "pricing-sync@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id)
    product.purchase_price = Decimal("700.00")
    await db_session.commit()

    def payload(**extra: Any) -> dict[str, Any]:
        return {
            "id": str(product.id),
            "name": "Renommé",
            "unit_price": "1200.00",
            "client_updated_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
            **extra,
        }

    headers = _headers(user.id, store.id)
    response = await client.put("/api/v1/sync/products", json=payload(), headers=headers)
    state = response.json()["server_state"]
    assert state["selling_price"] == "1200.00"
    assert state["purchase_price"] == "700.00"

    response = await client.put(
        "/api/v1/sync/products", json=payload(purchase_price=None), headers=headers
    )
    assert response.json()["server_state"]["purchase_price"] is None


def test_bulk_import_purchase_and_legacy_columns() -> None:
    """Nouveau modèle (purchase/selling) et ancienne colonne unit_price."""
    rows = parse_bulk_import_file(
        "p.csv", b"name,purchase_price,selling_price\nRiz,2800,3500\nSel,,100\n"
    )
    assert rows[0][1] is not None
    assert rows[0][1].purchase_price == Decimal("2800")
    assert rows[0][1].selling_price == Decimal("3500")
    assert rows[1][1] is not None
    assert rows[1][1].purchase_price is None

    legacy = parse_bulk_import_file("p.csv", b"name,unit_price\nRiz,3500\n")
    assert legacy[0][1] is not None
    assert legacy[0][1].selling_price == Decimal("3500")


# ---------------------------------------------------------------------------
# Ventes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sale_with_line_and_global_discount(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Instantané complet stocké et renvoyé tel quel (prix, coût, réductions)."""
    user = await _create_user(db_session, "pricing-sale@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    item = _item(
        purchase_price_at_sale="1500.00",
        discount_type="percentage",
        discount_value="10",
        discount_amount="400.00",
        line_total="3600.00",
    )
    response = await client.post(
        "/api/v1/sales",
        json=_sale(
            [item],
            "3500.00",
            discount_type="amount",
            discount_value="100",
            discount_amount="100.00",
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["total_amount"] == "3500.00"
    assert data["discount_type"] == "amount"
    assert data["discount_amount"] == "100.00"
    line = data["items"][0]
    assert line["unit_price_at_sale"] == "2000.00"
    assert line["purchase_price_at_sale"] == "1500.00"
    assert line["discount_type"] == "percentage"
    assert line["discount_amount"] == "400.00"
    assert line["line_total"] == "3600.00"

    pdf = await client.get(
        f"/api/v1/sales/{data['id']}/receipt", headers=_headers(user.id, store.id)
    )
    assert pdf.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item", "total", "sale_extra"),
    [
        # Réduction supérieure au brut.
        (
            _item(
                discount_type="amount",
                discount_value="5000",
                discount_amount="4000.00",
                line_total="0.00",
            ),
            "0.00",
            {},
        ),
        # Montant incohérent avec le pourcentage.
        (
            _item(
                discount_type="percentage",
                discount_value="10",
                discount_amount="300.00",
                line_total="3700.00",
            ),
            "3700.00",
            {},
        ),
        # line_total qui ignore la réduction.
        (
            _item(discount_type="amount", discount_value="500", discount_amount="500.00"),
            "4000.00",
            {},
        ),
        # Montant sans type.
        (_item(discount_amount="100.00", line_total="3900.00"), "3900.00", {}),
        # Total qui ignore la remise globale.
        (
            _item(),
            "4000.00",
            {"discount_type": "amount", "discount_value": "500", "discount_amount": "500.00"},
        ),
        # Pourcentage > 100.
        (
            _item(),
            "0.00",
            {"discount_type": "percentage", "discount_value": "150", "discount_amount": "4000.00"},
        ),
    ],
)
async def test_sale_invalid_discounts_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    item: dict[str, Any],
    total: str,
    sale_extra: dict[str, Any],
) -> None:
    user = await _create_user(db_session, f"pricing-invalid-{uuid4()}@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sales",
        json=_sale([item], total, **sale_extra),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422
