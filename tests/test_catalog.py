"""Tests d'intégration du module catalog."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.inventory.models import StockMovement
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
    barcode: str | None = None,
    current_stock: int | None = None,
    min_stock: int | None = None,
) -> Product:
    product = Product(
        store_id=store_id,
        name=name,
        unit_price=unit_price,
        barcode=barcode,
        current_stock=current_stock,
        min_stock=min_stock,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return product


def _headers(user_id: UUID, store_id: UUID) -> dict[str, str]:
    token = create_access_token(user_id, store_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /api/v1/products
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_product_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST avec données complètes → 201, tous les champs présents."""
    user = await _create_user(db_session, "create-ok@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={
            "name": "Pain de sucre",
            "barcode": "3017620422003",
            "unit_price": "500.00",
            "current_stock": 10,
        },
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pain de sucre"
    assert data["barcode"] == "3017620422003"
    assert data["unit_price"] == "500.00"
    assert data["current_stock"] == 10
    assert data["store_id"] == str(store.id)


@pytest.mark.asyncio
async def test_create_product_minimal(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST avec juste name + unit_price → 201, barcode et stock nuls."""
    user = await _create_user(db_session, "create-min@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Sel", "unit_price": "100.00"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sel"
    assert data["barcode"] is None
    assert data["current_stock"] is None


@pytest.mark.asyncio
async def test_create_product_invalid_price_negative(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST avec unit_price négatif → 422 (validation Pydantic)."""
    user = await _create_user(db_session, "create-neg@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Produit", "unit_price": "-100.00"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_product_with_min_stock(client: AsyncClient, db_session: AsyncSession) -> None:
    """POST avec min_stock → 201, champ présent dans la réponse."""
    user = await _create_user(db_session, "create-min-stock@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Riz local 5kg", "unit_price": "3500.00", "min_stock": 10},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    assert response.json()["min_stock"] == 10


@pytest.mark.asyncio
async def test_create_product_invalid_min_stock_negative(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST avec min_stock négatif → 422 (validation Pydantic)."""
    user = await _create_user(db_session, "create-min-stock-neg@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products",
        json={"name": "Produit", "unit_price": "100.00", "min_stock": -5},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_product_duplicate_barcode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """2 produits avec le même barcode → 1er 201, 2ème 409 avec field=barcode."""
    user = await _create_user(db_session, "dup-barcode@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)

    r1 = await client.post(
        "/api/v1/products",
        json={"name": "Produit A", "unit_price": "500.00", "barcode": "EAN8001234"},
        headers=headers,
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/v1/products",
        json={"name": "Produit B", "unit_price": "500.00", "barcode": "EAN8001234"},
        headers=headers,
    )
    assert r2.status_code == 409
    assert r2.json()["field"] == "barcode"


# ---------------------------------------------------------------------------
# POST /api/v1/products/bulk
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_create_all_valid(client: AsyncClient, db_session: AsyncSession) -> None:
    """Batch de 3 produits valides -> 200, tous created."""
    user = await _create_user(db_session, "bulk-ok@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={
            "items": [
                {"name": "Riz", "unit_price": "500.00"},
                {"name": "Huile", "unit_price": "1500.00"},
                {"name": "Sucre", "unit_price": "800.00"},
            ]
        },
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 3
    assert data["created_count"] == 3
    assert data["failed_count"] == 0
    assert all(r["status"] == "created" for r in data["results"])


@pytest.mark.asyncio
async def test_bulk_create_with_min_stock(client: AsyncClient, db_session: AsyncSession) -> None:
    """Batch avec min_stock -> champ appliqué sur le produit créé."""
    user = await _create_user(db_session, "bulk-min-stock@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={"items": [{"name": "Riz local 5kg", "unit_price": "3500.00", "min_stock": 10}]},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["results"][0]["product"]["min_stock"] == 10


@pytest.mark.asyncio
async def test_bulk_create_existing_barcode_conflict_isolated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Barcode déjà pris par un produit existant -> cette ligne failed, les autres created."""
    user = await _create_user(db_session, "bulk-conflict@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, "Déjà là", barcode="TAKEN1234567")
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={
            "items": [
                {"name": "Nouveau A", "unit_price": "500.00"},
                {"name": "Conflit", "unit_price": "500.00", "barcode": "TAKEN1234567"},
                {"name": "Nouveau B", "unit_price": "500.00"},
            ]
        },
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2
    assert data["failed_count"] == 1
    assert data["results"][0]["status"] == "created"
    assert data["results"][1]["status"] == "failed"
    assert data["results"][1]["field"] == "barcode"
    assert data["results"][2]["status"] == "created"


@pytest.mark.asyncio
async def test_bulk_create_intra_batch_duplicate_barcode(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Deux items du même batch avec le même barcode -> 1er created, 2ème failed."""
    user = await _create_user(db_session, "bulk-intra-dup@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={
            "items": [
                {"name": "Premier", "unit_price": "500.00", "barcode": "DUP1234567"},
                {"name": "Deuxième", "unit_price": "500.00", "barcode": "DUP1234567"},
            ]
        },
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["status"] == "created"
    assert data["results"][1]["status"] == "failed"
    assert data["results"][1]["field"] == "barcode"


@pytest.mark.asyncio
async def test_bulk_create_with_initial_stock_records_movement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Item avec current_stock -> mouvement catalog_update tracé (cohérence ADR-0007)."""
    user = await _create_user(db_session, "bulk-stock@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={"items": [{"name": "Riz", "unit_price": "500.00", "current_stock": 40}]},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    product_id = response.json()["results"][0]["product"]["id"]

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == UUID(product_id))
    )
    movements = result.scalars().all()
    assert len(movements) == 1
    assert movements[0].reason == "catalog_update"
    assert movements[0].quantity_delta == 40
    assert movements[0].resulting_stock == 40


@pytest.mark.asyncio
async def test_bulk_create_invalid_field_rejects_whole_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """unit_price négatif sur une ligne -> 422 sur toute la requête (pas de traitement partiel)."""
    user = await _create_user(db_session, "bulk-invalid@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={
            "items": [
                {"name": "Valide", "unit_price": "500.00"},
                {"name": "Invalide", "unit_price": "-100.00"},
            ]
        },
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422

    result = await db_session.execute(select(Product).where(Product.store_id == store.id))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_bulk_create_scoped_to_own_store(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Les produits importés sont rattachés à la boutique de l'appelant (RLS)."""
    user = await _create_user(db_session, "bulk-rls@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk",
        json={"items": [{"name": "Riz", "unit_price": "500.00"}]},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["product"]["store_id"] == str(store.id)


# ---------------------------------------------------------------------------
# POST /api/v1/products/bulk/file + GET /api/v1/products/bulk/template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_import_from_csv_file(client: AsyncClient, db_session: AsyncSession) -> None:
    """Upload CSV valide -> produits créés, réponse cohérente avec l'endpoint JSON."""
    user = await _create_user(db_session, "bulk-file-ok@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    csv_content = "name,barcode,unit_price,current_stock\nRiz,,3500.00,50\nHuile,,1500.00,30\n"

    response = await client.post(
        "/api/v1/products/bulk/file",
        files={"file": ("produits.csv", csv_content.encode(), "text/csv")},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2
    assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_bulk_import_from_csv_file_isolates_invalid_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Une ligne invalide au milieu d'un fichier -> failed pour cette ligne, les autres created."""
    user = await _create_user(db_session, "bulk-file-partial@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    csv_content = (
        "name,barcode,unit_price,current_stock\n"
        "Valide A,,500.00,10\n"
        "Invalide,,pas-un-prix,10\n"
        "Valide B,,800.00,5\n"
    )

    response = await client.post(
        "/api/v1/products/bulk/file",
        files={"file": ("produits.csv", csv_content.encode(), "text/csv")},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 2
    assert data["failed_count"] == 1
    assert data["results"][0]["status"] == "created"
    assert data["results"][1]["status"] == "failed"
    assert data["results"][2]["status"] == "created"


@pytest.mark.asyncio
async def test_bulk_import_unsupported_extension(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Extension non supportée -> 422."""
    user = await _create_user(db_session, "bulk-file-badext@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/products/bulk/file",
        files={"file": ("produits.txt", b"name,unit_price\nA,1\n", "text/plain")},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_bulk_import_template_csv(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /bulk/template?format=csv -> 200, téléchargeable, réutilisable pour un import."""
    user = await _create_user(db_session, "template-csv@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/products/bulk/template?format=csv", headers=_headers(user.id, store.id)
    )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["content-disposition"].endswith('.csv"')

    upload = await client.post(
        "/api/v1/products/bulk/file",
        files={"file": ("template-import-produits.csv", response.content, "text/csv")},
        headers=_headers(user.id, store.id),
    )
    assert upload.status_code == 200
    assert upload.json()["created_count"] == 2


@pytest.mark.asyncio
async def test_bulk_import_template_xlsx(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /bulk/template?format=xlsx -> 200, content-type Excel."""
    user = await _create_user(db_session, "template-xlsx@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/products/bulk/template?format=xlsx", headers=_headers(user.id, store.id)
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert response.headers["content-disposition"].endswith('.xlsx"')


# ---------------------------------------------------------------------------
# GET /api/v1/products/{product_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_product_by_id_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET par id → 200 avec le produit correspondant."""
    user = await _create_user(db_session, "get-id-ok@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Biscuits")
    await db_session.commit()

    response = await client.get(
        f"/api/v1/products/{product.id}",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(product.id)


@pytest.mark.asyncio
async def test_get_product_by_id_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET avec UUID inexistant → 404."""
    user = await _create_user(db_session, "get-id-404@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/products/{uuid4()}",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/products/by-barcode/{barcode}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_product_by_barcode_success(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /by-barcode/{code} → 200 avec le bon produit."""
    user = await _create_user(db_session, "barcode-ok@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Coca-Cola", barcode="5449000000996")
    await db_session.commit()

    response = await client.get(
        "/api/v1/products/by-barcode/5449000000996",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(product.id)


@pytest.mark.asyncio
async def test_get_product_by_barcode_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """GET /by-barcode/INEXISTANT → 404."""
    user = await _create_user(db_session, "barcode-404@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/products/by-barcode/NOPE123456",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/products/{product_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_product_partial(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH avec seulement le name → name modifié, price et stock intacts."""
    user = await _create_user(db_session, "patch-ok@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(
        db_session, store.id, "Ancien nom", unit_price=Decimal("200.00"), current_stock=5
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "Nouveau nom"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nouveau nom"
    assert data["unit_price"] == "200.00"
    assert data["current_stock"] == 5


@pytest.mark.asyncio
async def test_update_product_change_barcode(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH change le barcode → 200, nouveau barcode retourné."""
    user = await _create_user(db_session, "patch-barcode@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Produit", barcode="OLD1234567")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"barcode": "NEW9876543"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["barcode"] == "NEW9876543"


@pytest.mark.asyncio
async def test_update_product_barcode_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH avec barcode déjà pris par un autre produit → 409."""
    user = await _create_user(db_session, "patch-conflict@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, "Produit A", barcode="TAKEN12345")
    product_b = await _create_product(db_session, store.id, "Produit B")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product_b.id}",
        json={"barcode": "TAKEN12345"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 409
    assert response.json()["field"] == "barcode"


# ---------------------------------------------------------------------------
# PATCH current_stock -> traçabilité stock_movements
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_current_stock_records_movement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH avec current_stock -> un mouvement catalog_update est créé."""
    user = await _create_user(db_session, "patch-stock-track@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=10)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"current_stock": 25},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["current_stock"] == 25

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == product.id)
    )
    movements = result.scalars().all()
    assert len(movements) == 1
    assert movements[0].reason == "catalog_update"
    assert movements[0].quantity_delta == 15
    assert movements[0].resulting_stock == 25


@pytest.mark.asyncio
async def test_patch_without_current_stock_records_no_movement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH omettant current_stock -> aucun mouvement (exclude_unset respecté)."""
    user = await _create_user(db_session, "patch-stock-omit@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=10)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "Nouveau nom"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["current_stock"] == 10

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == product.id)
    )
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_patch_current_stock_null_disables_tracking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH current_stock: null -> tracking désactivé, mouvement delta=None tracé."""
    user = await _create_user(db_session, "patch-stock-disable@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=10)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"current_stock": None},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["current_stock"] is None

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == product.id)
    )
    movements = result.scalars().all()
    assert len(movements) == 1
    assert movements[0].reason == "catalog_update"
    assert movements[0].quantity_delta is None
    assert movements[0].resulting_stock is None


@pytest.mark.asyncio
async def test_patch_current_stock_same_value_records_no_movement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH avec la même valeur de current_stock -> no-op, aucun mouvement."""
    user = await _create_user(db_session, "patch-stock-noop@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=10)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"current_stock": 10},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == product.id)
    )
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_patch_min_stock_records_no_movement(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """PATCH min_stock -> champ déclaratif, aucun StockMovement (contrairement à current_stock)."""
    user = await _create_user(db_session, "patch-min-stock@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, current_stock=10)
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"min_stock": 5},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["min_stock"] == 5

    result = await db_session.execute(
        select(StockMovement).where(StockMovement.product_id == product.id)
    )
    assert result.scalars().all() == []


# ---------------------------------------------------------------------------
# DELETE /api/v1/products/{product_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_product(client: AsyncClient, db_session: AsyncSession) -> None:
    """DELETE → 204 No Content."""
    user = await _create_user(db_session, "delete-ok@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "À supprimer")
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/products/{product.id}",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_deleted_product_not_in_list(client: AsyncClient, db_session: AsyncSession) -> None:
    """Créer, supprimer, lister → produit absent de la liste."""
    user = await _create_user(db_session, "del-list@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Produit fantôme")
    await db_session.commit()

    headers = _headers(user.id, store.id)
    await client.delete(f"/api/v1/products/{product.id}", headers=headers)

    response = await client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert str(product.id) not in ids


@pytest.mark.asyncio
async def test_deleted_product_not_findable_by_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Créer, supprimer, GET by id → 404."""
    user = await _create_user(db_session, "del-get@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Produit effacé")
    await db_session.commit()

    headers = _headers(user.id, store.id)
    await client.delete(f"/api/v1/products/{product.id}", headers=headers)

    response = await client.get(f"/api/v1/products/{product.id}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleted_product_barcode_can_be_reused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Soft delete libère le barcode : un nouveau produit peut le reprendre → 201."""
    user = await _create_user(db_session, "del-barcode-reuse@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, "Premier", barcode="REUSE1234567")
    await db_session.commit()

    headers = _headers(user.id, store.id)
    await client.delete(f"/api/v1/products/{product.id}", headers=headers)

    r2 = await client.post(
        "/api/v1/products",
        json={"name": "Second", "unit_price": "100.00", "barcode": "REUSE1234567"},
        headers=headers,
    )
    assert r2.status_code == 201


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_products_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    """60 produits + limit=20 → 20 items, has_more=True, next_cursor non nul."""
    user = await _create_user(db_session, "paginate@test.com")
    store = await _create_store(db_session, user.id)
    for i in range(60):
        await _create_product(db_session, store.id, f"Produit {i:02d}")
    await db_session.commit()

    response = await client.get(
        "/api/v1/products?limit=20",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 20
    assert data["has_more"] is True
    assert data["next_cursor"] is not None


@pytest.mark.asyncio
async def test_list_products_with_cursor(client: AsyncClient, db_session: AsyncSession) -> None:
    """Page 1 avec cursor → page 2 sans chevauchement."""
    user = await _create_user(db_session, "paginate-cursor@test.com")
    store = await _create_store(db_session, user.id)
    for i in range(30):
        await _create_product(db_session, store.id, f"Item {i:02d}")
    await db_session.commit()

    headers = _headers(user.id, store.id)

    page1 = await client.get("/api/v1/products?limit=10", headers=headers)
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1["items"]) == 10
    assert data1["has_more"] is True

    page2 = await client.get(
        f"/api/v1/products?limit=10&cursor={data1['next_cursor']}", headers=headers
    )
    assert page2.status_code == 200
    data2 = page2.json()
    assert len(data2["items"]) == 10

    ids1 = {item["id"] for item in data1["items"]}
    ids2 = {item["id"] for item in data2["items"]}
    assert ids1.isdisjoint(ids2), "Les deux pages ne doivent pas avoir d'items en commun"


@pytest.mark.asyncio
async def test_list_products_search(client: AsyncClient, db_session: AsyncSession) -> None:
    """search=pa → seul 'Pain' retourné (ILIKE insensible à la casse)."""
    user = await _create_user(db_session, "search@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, "Pain")
    await _create_product(db_session, store.id, "Lait")
    await _create_product(db_session, store.id, "Café")
    await db_session.commit()

    response = await client.get(
        "/api/v1/products?search=pa",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Pain"


@pytest.mark.asyncio
async def test_list_products_empty_after_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """search avec terme inexistant → liste vide, has_more=False."""
    user = await _create_user(db_session, "search-empty@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, "Banane")
    await db_session.commit()

    response = await client.get(
        "/api/v1/products?search=zzz_inexistant",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_products_low_stock_only(client: AsyncClient, db_session: AsyncSession) -> None:
    """low_stock_only=true -> seuls les produits avec current_stock <= min_stock (tous deux non-NULL)."""
    user = await _create_user(db_session, "low-stock@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, "Sous seuil", current_stock=2, min_stock=5)
    await _create_product(db_session, store.id, "Au seuil", current_stock=5, min_stock=5)
    await _create_product(db_session, store.id, "Au dessus", current_stock=20, min_stock=5)
    await _create_product(db_session, store.id, "Pas de seuil", current_stock=1, min_stock=None)
    await _create_product(
        db_session, store.id, "Pas de stock suivi", current_stock=None, min_stock=5
    )
    await db_session.commit()

    response = await client.get(
        "/api/v1/products?low_stock_only=true",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert names == {"Sous seuil", "Au seuil"}


# ---------------------------------------------------------------------------
# Isolation tenant (CRITIQUE)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_a_cannot_get_product_of_user_b_by_id(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A avec son JWT ne peut pas lire le produit de B → 404 (pas 403)."""
    user_a = await _create_user(db_session, "iso-a-get@test.com")
    user_b = await _create_user(db_session, "iso-b-get@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_b = await _create_product(db_session, store_b.id, "Produit de B")
    await db_session.commit()

    response = await client.get(
        f"/api/v1/products/{product_b.id}",
        headers=_headers(user_a.id, store_a.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_update_product_of_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A ne peut pas modifier le produit de B → 404."""
    user_a = await _create_user(db_session, "iso-a-patch@test.com")
    user_b = await _create_user(db_session, "iso-b-patch@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_b = await _create_product(db_session, store_b.id, "Produit de B")
    await db_session.commit()

    response = await client.patch(
        f"/api/v1/products/{product_b.id}",
        json={"name": "Hacked"},
        headers=_headers(user_a.id, store_a.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_delete_product_of_user_b(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """User A ne peut pas supprimer le produit de B → 404."""
    user_a = await _create_user(db_session, "iso-a-del@test.com")
    user_b = await _create_user(db_session, "iso-b-del@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_b = await _create_product(db_session, store_b.id, "Produit de B")
    await db_session.commit()

    response = await client.delete(
        f"/api/v1/products/{product_b.id}",
        headers=_headers(user_a.id, store_a.id),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_a_list_does_not_include_user_b_products(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La liste de A ne contient QUE les produits de A, jamais ceux de B."""
    user_a = await _create_user(db_session, "iso-a-list@test.com")
    user_b = await _create_user(db_session, "iso-b-list@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    product_a = await _create_product(db_session, store_a.id, "Produit de A")
    product_b = await _create_product(db_session, store_b.id, "Produit de B")
    await db_session.commit()

    response = await client.get(
        "/api/v1/products",
        headers=_headers(user_a.id, store_a.id),
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(product_a.id) in ids
    assert str(product_b.id) not in ids
