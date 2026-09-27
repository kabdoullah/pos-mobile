"""Tests des catégories de produits (ADR-0008) : API, lien produit, synchro."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import encode_cursor
from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _store(db: AsyncSession, email: str) -> tuple[User, Store]:
    user = User(
        email=email, password_hash=_DUMMY_HASH, phone_number=f"+225{abs(hash(email)) % 10**9:09d}"
    )
    db.add(user)
    await db.flush()
    store = Store(owner_id=user.id, name=f"Boutique {email}")
    db.add(store)
    await db.flush()
    await db.commit()
    return user, store


def _headers(user: User, store: Store) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, store.id)}"}


async def _category(db: AsyncSession, store: Store, name: str) -> Category:
    category = Category(store_id=store.id, name=name)
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


def _category_payload(
    *,
    category_id: UUID | None = None,
    name: str = "Boissons",
    client_updated_at: datetime | None = None,
    deleted: bool = False,
) -> dict[str, Any]:
    return {
        "id": str(category_id or uuid4()),
        "name": name,
        "client_updated_at": (client_updated_at or datetime.now(UTC)).isoformat(),
        "deleted": deleted,
    }


def _product_payload(product_id: UUID, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(product_id),
        "name": "Coca-Cola",
        "unit_price": "500.00",
        "client_updated_at": datetime.now(UTC).isoformat(),
        "deleted": False,
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# API /api/v1/categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_list_rename_category(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "cat-crud@test.com")
    headers = _headers(user, store)

    r = await client.post("/api/v1/categories", json={"name": "  Boissons "}, headers=headers)
    assert r.status_code == 201
    category_id = r.json()["id"]
    assert r.json()["name"] == "Boissons"

    await client.post("/api/v1/categories", json={"name": "alimentation"}, headers=headers)

    r = await client.get("/api/v1/categories", headers=headers)
    assert r.status_code == 200
    # Tri par nom insensible à la casse.
    assert [c["name"] for c in r.json()] == ["alimentation", "Boissons"]

    r = await client.patch(
        f"/api/v1/categories/{category_id}", json={"name": "Boissons fraîches"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Boissons fraîches"


@pytest.mark.asyncio
async def test_category_name_unique_case_insensitive(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-unique@test.com")
    headers = _headers(user, store)

    await client.post("/api/v1/categories", json={"name": "Boissons"}, headers=headers)
    r = await client.post("/api/v1/categories", json={"name": "BOISSONS"}, headers=headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_deleted_category_frees_its_name(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-free-name@test.com")
    headers = _headers(user, store)

    r = await client.post("/api/v1/categories", json={"name": "Hygiène"}, headers=headers)
    r = await client.delete(f"/api/v1/categories/{r.json()['id']}", headers=headers)
    assert r.status_code == 204

    r = await client.post("/api/v1/categories", json={"name": "Hygiène"}, headers=headers)
    assert r.status_code == 201
    r = await client.get("/api/v1/categories", headers=headers)
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_same_name_allowed_in_two_stores(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_a, store_a = await _store(db_session, "cat-two-a@test.com")
    user_b, store_b = await _store(db_session, "cat-two-b@test.com")

    r_a = await client.post(
        "/api/v1/categories", json={"name": "Boissons"}, headers=_headers(user_a, store_a)
    )
    r_b = await client.post(
        "/api/v1/categories", json={"name": "Boissons"}, headers=_headers(user_b, store_b)
    )
    assert r_a.status_code == 201
    assert r_b.status_code == 201


@pytest.mark.asyncio
async def test_delete_category_detaches_products_and_bumps_them(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-detach@test.com")
    headers = _headers(user, store)
    category = await _category(db_session, store, "Boissons")
    # Date passée explicite : l'INSERT la conserve (le trigger n'agit qu'à
    # l'UPDATE). Tout le test partage une transaction, où now() est figé.
    old = datetime.now(UTC) - timedelta(days=1)
    product = Product(
        store_id=store.id,
        name="Coca",
        unit_price=Decimal("500"),
        category_id=category.id,
        updated_at=old,
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.commit()

    r = await client.delete(f"/api/v1/categories/{category.id}", headers=headers)
    assert r.status_code == 204

    r = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert r.json()["category_id"] is None
    # updated_at bumpé : les autres appareils récupèrent la correction au pull.
    assert datetime.fromisoformat(r.json()["updated_at"]) > old


# ---------------------------------------------------------------------------
# Lien produit → catégorie (API produits)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_with_unknown_category_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-unknown@test.com")
    r = await client.post(
        "/api/v1/products",
        json={"name": "Coca", "unit_price": "500", "category_id": str(uuid4())},
        headers=_headers(user, store),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_product_cannot_use_category_of_another_store(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user_a, store_a = await _store(db_session, "cat-other-a@test.com")
    _, store_b = await _store(db_session, "cat-other-b@test.com")
    category_b = await _category(db_session, store_b, "Boissons B")
    await db_session.commit()

    r = await client.post(
        "/api/v1/products",
        json={"name": "Coca", "unit_price": "500", "category_id": str(category_b.id)},
        headers=_headers(user_a, store_a),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_product_category_set_and_clear(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-patch@test.com")
    headers = _headers(user, store)
    category_id = (
        await client.post("/api/v1/categories", json={"name": "Riz"}, headers=headers)
    ).json()["id"]
    product_id = (
        await client.post(
            "/api/v1/products", json={"name": "Riz 5kg", "unit_price": "8000"}, headers=headers
        )
    ).json()["id"]

    r = await client.patch(
        f"/api/v1/products/{product_id}", json={"category_id": category_id}, headers=headers
    )
    assert r.json()["category_id"] == category_id

    # Champ absent : inchangé.
    r = await client.patch(
        f"/api/v1/products/{product_id}", json={"name": "Riz 5 kg"}, headers=headers
    )
    assert r.json()["category_id"] == category_id

    # null explicite : retiré.
    r = await client.patch(
        f"/api/v1/products/{product_id}", json={"category_id": None}, headers=headers
    )
    assert r.json()["category_id"] is None


# ---------------------------------------------------------------------------
# Isolation RLS
# ---------------------------------------------------------------------------


async def _as_store(db: AsyncSession, store_id: UUID) -> None:
    await db.execute(text("SET LOCAL ROLE pos_app"))
    await db.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))


@pytest.mark.asyncio
async def test_rls_store_cannot_read_categories_of_another_store(
    db_session: AsyncSession,
) -> None:
    _, store_a = await _store(db_session, "cat-rls-read-a@test.com")
    _, store_b = await _store(db_session, "cat-rls-read-b@test.com")
    await _category(db_session, store_a, "Catégorie A")
    category_b = await _category(db_session, store_b, "Catégorie B")

    await _as_store(db_session, store_a.id)
    rows = (await db_session.execute(text("SELECT name FROM categories"))).fetchall()
    assert [r.name for r in rows] == ["Catégorie A"]
    hidden = await db_session.execute(
        text("SELECT id FROM categories WHERE id = :cid"), {"cid": str(category_b.id)}
    )
    assert hidden.fetchone() is None


@pytest.mark.asyncio
async def test_rls_store_cannot_insert_or_update_category_of_another_store(
    db_session: AsyncSession,
) -> None:
    _, store_a = await _store(db_session, "cat-rls-write-a@test.com")
    _, store_b = await _store(db_session, "cat-rls-write-b@test.com")
    category_b = await _category(db_session, store_b, "Catégorie B")

    await _as_store(db_session, store_a.id)
    updated = await db_session.execute(
        text("UPDATE categories SET name = 'piratée' WHERE id = :cid"),
        {"cid": str(category_b.id)},
    )
    assert updated.rowcount == 0

    with pytest.raises(ProgrammingError):
        await db_session.execute(
            text("INSERT INTO categories (id, store_id, name) VALUES (:id, :sid, 'Intrus')"),
            {"id": str(uuid4()), "sid": str(store_b.id)},
        )


# ---------------------------------------------------------------------------
# Synchro PUT /api/v1/sync/categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_category_create_then_update_then_delete(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-sync-flow@test.com")
    headers = _headers(user, store)
    category_id = uuid4()
    t0 = datetime.now(UTC) - timedelta(minutes=10)

    r = await client.put(
        "/api/v1/sync/categories",
        json=_category_payload(category_id=category_id, name="Boissons", client_updated_at=t0),
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["status"] == "created"

    r = await client.put(
        "/api/v1/sync/categories",
        json=_category_payload(
            category_id=category_id,
            name="Boissons fraîches",
            client_updated_at=datetime.now(UTC) + timedelta(seconds=1),
        ),
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "updated"
    assert r.json()["server_state"]["name"] == "Boissons fraîches"

    r = await client.put(
        "/api/v1/sync/categories",
        json=_category_payload(
            category_id=category_id,
            name="Boissons fraîches",
            client_updated_at=datetime.now(UTC) + timedelta(seconds=2),
            deleted=True,
        ),
        headers=headers,
    )
    assert r.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_sync_category_older_state_is_a_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-sync-older@test.com")
    category = await _category(db_session, store, "Boissons")
    await db_session.commit()

    r = await client.put(
        "/api/v1/sync/categories",
        json=_category_payload(
            category_id=category.id,
            name="Ancien nom",
            client_updated_at=category.updated_at - timedelta(minutes=5),
        ),
        headers=_headers(user, store),
    )
    assert r.status_code == 409
    assert r.json()["server_state"]["name"] == "Boissons"


@pytest.mark.asyncio
async def test_sync_category_name_taken_is_a_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-sync-name@test.com")
    await _category(db_session, store, "Boissons")
    await db_session.commit()

    r = await client.put(
        "/api/v1/sync/categories",
        json=_category_payload(name="boissons"),
        headers=_headers(user, store),
    )
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# Synchro produits avec catégorie
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_product_with_category(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "cat-sync-product@test.com")
    category = await _category(db_session, store, "Boissons")
    await db_session.commit()

    r = await client.put(
        "/api/v1/sync/products",
        json=_product_payload(uuid4(), category_id=str(category.id)),
        headers=_headers(user, store),
    )
    assert r.status_code == 201
    assert r.json()["server_state"]["category_id"] == str(category.id)


@pytest.mark.asyncio
async def test_sync_product_with_unknown_category_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Catégorie pas encore poussée : refus, le produit reste en attente côté app."""
    user, store = await _store(db_session, "cat-sync-422@test.com")
    r = await client.put(
        "/api/v1/sync/products",
        json=_product_payload(uuid4(), category_id=str(uuid4())),
        headers=_headers(user, store),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_sync_product_without_category_field_keeps_category(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Une ancienne version de l'app (sans category_id) n'efface pas la catégorie."""
    user, store = await _store(db_session, "cat-sync-compat@test.com")
    category = await _category(db_session, store, "Boissons")
    product = Product(
        store_id=store.id, name="Coca", unit_price=Decimal("500"), category_id=category.id
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)
    await db_session.commit()

    payload = _product_payload(product.id, name="Coca-Cola 33cl")
    payload["client_updated_at"] = (product.updated_at + timedelta(seconds=5)).isoformat()
    assert "category_id" not in payload

    r = await client.put("/api/v1/sync/products", json=payload, headers=_headers(user, store))
    assert r.status_code == 200
    assert r.json()["server_state"]["name"] == "Coca-Cola 33cl"
    assert r.json()["server_state"]["category_id"] == str(category.id)


@pytest.mark.asyncio
async def test_sync_product_with_deleted_category_gets_none(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Catégorie supprimée ailleurs entre-temps : la suppression l'emporte."""
    user, store = await _store(db_session, "cat-sync-deleted@test.com")
    category = await _category(db_session, store, "Boissons")
    category.deleted_at = datetime.now(UTC)
    await db_session.flush()
    await db_session.commit()

    r = await client.put(
        "/api/v1/sync/products",
        json=_product_payload(uuid4(), category_id=str(category.id)),
        headers=_headers(user, store),
    )
    assert r.status_code == 201
    assert r.json()["server_state"]["category_id"] is None


# ---------------------------------------------------------------------------
# Pull GET /api/v1/sync/changes : phase catégories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_changes_returns_categories_before_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "cat-changes@test.com")
    category = await _category(db_session, store, "Boissons")
    db_session.add(
        Product(store_id=store.id, name="Coca", unit_price=Decimal("500"), category_id=category.id)
    )
    await db_session.flush()

    r = await client.get("/api/v1/sync/changes", headers=_headers(user, store))
    assert r.status_code == 200
    data = r.json()
    assert [c["name"] for c in data["categories"]] == ["Boissons"]
    assert data["products"][0]["category_id"] == str(category.id)


@pytest.mark.asyncio
async def test_sync_changes_paginates_across_all_phases(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """3 catégories + 4 produits, limit=2 : tout est récupéré une seule fois."""
    user, store = await _store(db_session, "cat-changes-paging@test.com")
    for i in range(3):
        db_session.add(Category(store_id=store.id, name=f"Catégorie {i}"))
    for i in range(4):
        db_session.add(Product(store_id=store.id, name=f"Produit {i}", unit_price=Decimal("100")))
    await db_session.flush()

    headers = _headers(user, store)
    categories: list[str] = []
    products: list[str] = []
    cursor: str | None = None
    for _ in range(10):
        params: dict[str, Any] = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        data = (await client.get("/api/v1/sync/changes", params=params, headers=headers)).json()
        categories += [c["id"] for c in data["categories"]]
        products += [p["id"] for p in data["products"]]
        if not data["has_more"]:
            break
        cursor = data["next_cursor"]

    assert len(categories) == len(set(categories)) == 3
    assert len(products) == len(set(products)) == 4


@pytest.mark.asyncio
async def test_sync_changes_accepts_cursor_emitted_before_categories(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un cursor « phase products » d'une ancienne app reste valide."""
    user, store = await _store(db_session, "cat-changes-old-cursor@test.com")
    await _category(db_session, store, "Boissons")
    db_session.add(Product(store_id=store.id, name="Coca", unit_price=Decimal("500")))
    await db_session.flush()

    r = await client.get(
        "/api/v1/sync/changes",
        params={"cursor": encode_cursor({"phase": "products"})},
        headers=_headers(user, store),
    )
    data = r.json()
    assert data["categories"] == []
    assert [p["name"] for p in data["products"]] == ["Coca"]
