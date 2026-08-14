"""Tests d'intégration du module inventory."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email, password_hash=_DUMMY_HASH, phone_number=f"+225{abs(hash(email)) % 10**9:09d}"
    )
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
    current_stock: int | None = None,
) -> Product:
    product = Product(
        store_id=store_id, name=name, unit_price=unit_price, current_stock=current_stock
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


def _headers(user_id: UUID, store_id: UUID) -> dict[str, str]:
    token = create_access_token(user_id, store_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /api/v1/inventory/movements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manual_adjustment_enables_tracking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ajustement manuel sur un produit non suivi -> active le tracking, 201."""
    user = await _create_user(db_session, "adj-enable@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=None)
    await db_session.commit()

    response = await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product.id), "quantity_delta": 10, "note": "stock initial"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["quantity_delta"] == 10
    assert data["resulting_stock"] == 10
    assert data["reason"] == "manual_adjustment"
    assert data["note"] == "stock initial"
    assert data["created_by"] == str(user.id)

    product_response = await client.get(
        f"/api/v1/products/{product.id}", headers=_headers(user.id, store.id)
    )
    assert product_response.json()["current_stock"] == 10


@pytest.mark.asyncio
async def test_manual_adjustment_zero_delta_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """quantity_delta=0 -> 422."""
    user = await _create_user(db_session, "adj-zero@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=5)
    await db_session.commit()

    response = await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product.id), "quantity_delta": 0},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_manual_adjustment_product_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """product_id inexistant -> 404."""
    user = await _create_user(db_session, "adj-404@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(uuid4()), "quantity_delta": 5},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manual_adjustment_allows_negative_stock(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Ajustement négatif dépassant le stock disponible -> succès, stock négatif."""
    user = await _create_user(db_session, "adj-negative@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=3)
    await db_session.commit()

    response = await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product.id), "quantity_delta": -10, "note": "casse"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["resulting_stock"] == -7


# ---------------------------------------------------------------------------
# GET /api/v1/inventory/movements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_movements_filter_by_product(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Filtre product_id -> ne retourne que les mouvements de ce produit."""
    user = await _create_user(db_session, "list-filter@test.com")
    store = await _create_store(db_session, user.id)
    product_a = await _create_product(db_session, store.id, "A", current_stock=0)
    product_b = await _create_product(db_session, store.id, "B", current_stock=0)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product_a.id), "quantity_delta": 5},
        headers=headers,
    )
    await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product_b.id), "quantity_delta": 7},
        headers=headers,
    )

    response = await client.get(
        f"/api/v1/inventory/movements?product_id={product_a.id}", headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["product_id"] == str(product_a.id)


@pytest.mark.asyncio
async def test_list_movements_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    """60 ajustements + limit=20 -> 20 items, has_more=True."""
    user = await _create_user(db_session, "list-paginate@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=0)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    for _ in range(60):
        await client.post(
            "/api/v1/inventory/movements",
            json={"product_id": str(product.id), "quantity_delta": 1},
            headers=headers,
        )

    response = await client.get("/api/v1/inventory/movements?limit=20", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 20
    assert data["has_more"] is True
    assert data["next_cursor"] is not None


# ---------------------------------------------------------------------------
# Isolation tenant (CRITIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_a_cannot_adjust_stock_of_product_of_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A ne peut pas ajuster le stock d'un produit de B -> 404 (pas 403)."""
    user_a = await _create_user(db_session, "iso-a-adj@test.com")
    user_b = await _create_user(db_session, "iso-b-adj@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_b = await _create_product(db_session, store_b.id, "Produit de B", current_stock=5)
    await db_session.commit()

    response = await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product_b.id), "quantity_delta": 5},
        headers=_headers(user_a.id, store_a.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_a_list_does_not_include_user_b_movements(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La liste de A ne contient jamais les mouvements de B."""
    user_a = await _create_user(db_session, "iso-a-list@test.com")
    user_b = await _create_user(db_session, "iso-b-list@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_a = await _create_product(db_session, store_a.id, "Produit de A", current_stock=0)
    product_b = await _create_product(db_session, store_b.id, "Produit de B", current_stock=0)
    await db_session.commit()

    await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product_a.id), "quantity_delta": 3},
        headers=_headers(user_a.id, store_a.id),
    )
    await client.post(
        "/api/v1/inventory/movements",
        json={"product_id": str(product_b.id), "quantity_delta": 3},
        headers=_headers(user_b.id, store_b.id),
    )

    response = await client.get(
        "/api/v1/inventory/movements", headers=_headers(user_a.id, store_a.id)
    )

    assert response.status_code == 200
    product_ids = {item["product_id"] for item in response.json()["items"]}
    assert product_ids == {str(product_a.id)}
