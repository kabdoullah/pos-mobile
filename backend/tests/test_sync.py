"""Tests d'intégration du module sync."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.sales.service import SaleService
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
    barcode: str | None = None,
) -> Product:
    product = Product(store_id=store_id, name=name, unit_price=unit_price, barcode=barcode)
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
) -> dict[str, Any]:
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


def _product_sync_payload(
    *,
    product_id: UUID | None = None,
    name: str = "Produit test",
    barcode: str | None = None,
    unit_price: str = "1000.00",
    current_stock: int | None = None,
    client_updated_at: str | None = None,
    deleted: bool = False,
) -> dict[str, Any]:
    if product_id is None:
        product_id = uuid4()
    if client_updated_at is None:
        client_updated_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "id": str(product_id),
        "name": name,
        "unit_price": unit_price,
        "deleted": deleted,
        "client_updated_at": client_updated_at,
    }
    if barcode is not None:
        payload["barcode"] = barcode
    if current_stock is not None:
        payload["current_stock"] = current_stock
    return payload


# ---------------------------------------------------------------------------
# POST /api/v1/sync/sales — Batch best-effort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_sales_batch_all_new(client: AsyncClient, db_session: AsyncSession) -> None:
    """3 ventes nouvelles → processed=3, tous created, receipt_numbers séquentiels."""
    user = await _create_user(db_session, "sync-batch-new@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    batch = {"sales": [_sale_payload(), _sale_payload(), _sale_payload()]}
    response = await client.post(
        "/api/v1/sync/sales", json=batch, headers=_headers(user.id, store.id)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 3
    assert all(r["status"] == "created" for r in data["results"])
    receipts = sorted(r["receipt_number"] for r in data["results"])
    assert receipts == list(range(receipts[0], receipts[0] + 3))


@pytest.mark.asyncio
async def test_sync_sales_batch_with_duplicate(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Même UUID deux fois dans le batch → 1 created + 1 already_exists, même receipt_number."""
    user = await _create_user(db_session, "sync-batch-dup@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    sale_id = uuid4()
    batch = {"sales": [_sale_payload(sale_id=sale_id), _sale_payload(sale_id=sale_id)]}

    response = await client.post(
        "/api/v1/sync/sales", json=batch, headers=_headers(user.id, store.id)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 2
    statuses = [r["status"] for r in data["results"]]
    assert "created" in statuses
    assert "already_exists" in statuses
    receipts = [r["receipt_number"] for r in data["results"]]
    assert receipts[0] == receipts[1]


@pytest.mark.asyncio
async def test_sync_sales_batch_idempotent_across_requests(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Même batch envoyé 2x → tous already_exists la 2ème fois, pas de doublons en DB."""
    user = await _create_user(db_session, "sync-batch-idem@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    headers = _headers(user.id, store.id)
    sale_ids = [uuid4() for _ in range(3)]
    batch = {"sales": [_sale_payload(sale_id=sid) for sid in sale_ids]}

    r1 = await client.post("/api/v1/sync/sales", json=batch, headers=headers)
    assert r1.status_code == 200
    assert all(r["status"] == "created" for r in r1.json()["results"])

    r2 = await client.post("/api/v1/sync/sales", json=batch, headers=headers)
    assert r2.status_code == 200
    assert all(r["status"] == "already_exists" for r in r2.json()["results"])

    count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM sales WHERE store_id = :sid"),
            {"sid": str(store.id)},
        )
    ).scalar()
    assert count == 3


@pytest.mark.asyncio
async def test_sync_sales_batch_mixed_valid_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Un create_sale force une exception de service → 2 created + 1 failed, batch retourne 200."""
    user = await _create_user(db_session, "sync-batch-mixed@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    sale_id_ok1 = uuid4()
    sale_id_fail = uuid4()
    sale_id_ok2 = uuid4()

    batch = {
        "sales": [
            _sale_payload(sale_id=sale_id_ok1),
            _sale_payload(sale_id=sale_id_fail),
            _sale_payload(sale_id=sale_id_ok2),
        ]
    }

    original_create = SaleService.create_sale

    async def patched_create(self: SaleService, store_id: UUID, payload: Any) -> Any:
        if payload.id == sale_id_fail:
            raise ValueError("Forced failure")
        return await original_create(self, store_id, payload)

    with patch.object(SaleService, "create_sale", patched_create):
        response = await client.post(
            "/api/v1/sync/sales", json=batch, headers=_headers(user.id, store.id)
        )

    assert response.status_code == 200
    data = response.json()
    assert data["processed"] == 3

    by_id = {r["id"]: r for r in data["results"]}
    assert by_id[str(sale_id_ok1)]["status"] == "created"
    assert by_id[str(sale_id_fail)]["status"] == "failed"
    assert by_id[str(sale_id_ok2)]["status"] == "created"


@pytest.mark.asyncio
async def test_sync_sales_batch_empty(client: AsyncClient, db_session: AsyncSession) -> None:
    """Batch vide → 422 (min_length=1)."""
    user = await _create_user(db_session, "sync-batch-empty@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/sync/sales",
        json={"sales": []},
        headers=_headers(user.id, store.id),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_sales_batch_too_large(client: AsyncClient, db_session: AsyncSession) -> None:
    """51 ventes → 422 (max_length=50)."""
    user = await _create_user(db_session, "sync-batch-large@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    batch = {"sales": [_sale_payload() for _ in range(51)]}
    response = await client.post(
        "/api/v1/sync/sales", json=batch, headers=_headers(user.id, store.id)
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_sales_batch_internal_error_isolated(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """RuntimeError sur 1 vente → failed avec error="Internal error", les autres OK."""
    user = await _create_user(db_session, "sync-batch-err@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    sale_id_ok = uuid4()
    sale_id_fail = uuid4()
    batch = {
        "sales": [
            _sale_payload(sale_id=sale_id_ok),
            _sale_payload(sale_id=sale_id_fail),
        ]
    }

    original_create = SaleService.create_sale

    async def patched_create(self: SaleService, store_id: UUID, payload: Any) -> Any:
        if payload.id == sale_id_fail:
            raise RuntimeError("Internal error")
        return await original_create(self, store_id, payload)

    with patch.object(SaleService, "create_sale", patched_create):
        response = await client.post(
            "/api/v1/sync/sales", json=batch, headers=_headers(user.id, store.id)
        )

    assert response.status_code == 200
    by_id = {r["id"]: r for r in response.json()["results"]}
    assert by_id[str(sale_id_ok)]["status"] == "created"
    assert by_id[str(sale_id_fail)]["status"] == "failed"
    assert by_id[str(sale_id_fail)]["error"] == "Internal error"


# ---------------------------------------------------------------------------
# PUT /api/v1/sync/products — Last-write-wins
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_product_create(client: AsyncClient, db_session: AsyncSession) -> None:
    """Produit nouveau → 201 created, server_state retourné avec le bon nom."""
    user = await _create_user(db_session, "sync-prod-create@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    product_id = uuid4()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(product_id=product_id, name="Nouveau produit"),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "created"
    assert data["id"] == str(product_id)
    assert data["server_state"] is not None
    assert data["server_state"]["name"] == "Nouveau produit"


@pytest.mark.asyncio
async def test_sync_product_create_barcode_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Nouveau produit avec barcode déjà utilisé par un autre produit actif → 409 conflict."""
    user = await _create_user(db_session, "sync-prod-bc-conflict@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, barcode="ABC123456")
    await db_session.commit()

    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(barcode="ABC123456"),  # UUID différent, même barcode
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 409
    assert response.json()["status"] == "conflict"


@pytest.mark.asyncio
async def test_sync_product_update_newer(client: AsyncClient, db_session: AsyncSession) -> None:
    """client_updated_at > server updated_at → 200 updated, nom mis à jour en DB."""
    user = await _create_user(db_session, "sync-prod-newer@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, name="Ancien nom")
    await db_session.commit()

    client_ts = (product.updated_at + timedelta(seconds=5)).isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            name="Nouveau nom",
            client_updated_at=client_ts,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"
    assert data["server_state"]["name"] == "Nouveau nom"


@pytest.mark.asyncio
async def test_sync_product_update_same_timestamp(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """client_updated_at == server updated_at → 200 no_change, nom inchangé en DB."""
    user = await _create_user(db_session, "sync-prod-same-ts@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, name="Nom stable")
    await db_session.commit()

    client_ts = product.updated_at.isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            name="Nom ignoré",
            client_updated_at=client_ts,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_change"

    await db_session.refresh(product)
    assert product.name == "Nom stable"


@pytest.mark.asyncio
async def test_sync_product_update_older(client: AsyncClient, db_session: AsyncSession) -> None:
    """client_updated_at < server updated_at → 409 conflict, server_state retourné."""
    user = await _create_user(db_session, "sync-prod-older@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, name="Nom serveur")
    await db_session.commit()

    client_ts = (product.updated_at - timedelta(seconds=10)).isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            name="Nom client obsolète",
            client_updated_at=client_ts,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 409
    data = response.json()
    assert data["status"] == "conflict"
    assert data["server_state"] is not None
    assert data["server_state"]["name"] == "Nom serveur"


@pytest.mark.asyncio
async def test_sync_product_soft_delete(client: AsyncClient, db_session: AsyncSession) -> None:
    """deleted=True et client_ts > server → 200 deleted, deleted_at non nul en DB."""
    user = await _create_user(db_session, "sync-prod-delete@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id)
    await db_session.commit()

    client_ts = (product.updated_at + timedelta(seconds=5)).isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            client_updated_at=client_ts,
            deleted=True,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"
    assert data["server_state"] is None

    await db_session.refresh(product)
    assert product.deleted_at is not None


@pytest.mark.asyncio
async def test_sync_product_undelete(client: AsyncClient, db_session: AsyncSession) -> None:
    """Produit soft-deleted en DB, client envoie deleted=False avec ts plus récent → 200 updated."""
    user = await _create_user(db_session, "sync-prod-undelete@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, name="Produit ressuscité")
    product.deleted_at = datetime.now(UTC)
    await db_session.flush()
    await db_session.refresh(product)  # récupère updated_at mis à jour par le trigger
    await db_session.commit()

    client_ts = (product.updated_at + timedelta(seconds=5)).isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            name="Produit ressuscité",
            client_updated_at=client_ts,
            deleted=False,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "updated"

    await db_session.refresh(product)
    assert product.deleted_at is None


@pytest.mark.asyncio
async def test_sync_product_already_deleted(client: AsyncClient, db_session: AsyncSession) -> None:
    """Produit déjà soft-deleted, client envoie deleted=True → 200 no_change."""
    user = await _create_user(db_session, "sync-prod-already-del@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id)
    product.deleted_at = datetime.now(UTC)
    await db_session.flush()
    await db_session.refresh(product)
    await db_session.commit()

    client_ts = (product.updated_at + timedelta(seconds=5)).isoformat()
    response = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            client_updated_at=client_ts,
            deleted=True,
        ),
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_change"


@pytest.mark.asyncio
async def test_sync_product_invalid_timezone(client: AsyncClient, db_session: AsyncSession) -> None:
    """client_updated_at sans timezone → 422."""
    user = await _create_user(db_session, "sync-prod-no-tz@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    payload = _product_sync_payload()
    payload["client_updated_at"] = "2026-01-01T10:00:00"  # pas de timezone

    response = await client.put(
        "/api/v1/sync/products",
        json=payload,
        headers=_headers(user.id, store.id),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/sync/changes — Pull incrémental
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_changes_since_null(client: AsyncClient, db_session: AsyncSession) -> None:
    """since=null → retourne tous produits et ventes de la boutique."""
    user = await _create_user(db_session, "sync-changes-null@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id, name="Produit 1")
    await _create_product(db_session, store.id, name="Produit 2")
    await db_session.commit()

    headers = _headers(user.id, store.id)
    await client.post(
        "/api/v1/sync/sales",
        json={"sales": [_sale_payload()]},
        headers=headers,
    )

    response = await client.get("/api/v1/sync/changes", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 2
    assert len(data["sales"]) == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_sync_changes_since_now(client: AsyncClient, db_session: AsyncSession) -> None:
    """since=futur → listes vides."""
    user = await _create_user(db_session, "sync-changes-future@test.com")
    store = await _create_store(db_session, user.id)
    await _create_product(db_session, store.id)
    await db_session.commit()

    since = (datetime.now(UTC) + timedelta(minutes=1)).isoformat()
    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": since},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["products"] == []
    assert data["sales"] == []
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_sync_changes_product_recently_modified(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Produit créé après `since` → présent dans la réponse."""
    user = await _create_user(db_session, "sync-changes-prod-recent@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    product = await _create_product(db_session, store.id, name="Produit récent")

    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": since},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    product_ids = [p["id"] for p in response.json()["products"]]
    assert str(product.id) in product_ids


@pytest.mark.asyncio
async def test_sync_changes_sale_recently_synced(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Vente syncée après `since` → présente dans la réponse."""
    user = await _create_user(db_session, "sync-changes-sale-recent@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()
    headers = _headers(user.id, store.id)
    sale_id = uuid4()
    await client.post(
        "/api/v1/sync/sales",
        json={"sales": [_sale_payload(sale_id=sale_id)]},
        headers=headers,
    )

    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": since},
        headers=headers,
    )

    assert response.status_code == 200
    sale_ids = [s["id"] for s in response.json()["sales"]]
    assert str(sale_id) in sale_ids


@pytest.mark.asyncio
async def test_sync_changes_includes_soft_deleted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Produit soft-deleted → présent dans les changes avec deleted_at non nul."""
    user = await _create_user(db_session, "sync-changes-soft-del@test.com")
    store = await _create_store(db_session, user.id)
    product = await _create_product(db_session, store.id, name="À supprimer")
    await db_session.commit()

    headers = _headers(user.id, store.id)
    since = (datetime.now(UTC) - timedelta(seconds=2)).isoformat()

    # Soft-delete via l'endpoint sync (client plus récent)
    await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(
            product_id=product.id,
            client_updated_at=(product.updated_at + timedelta(seconds=5)).isoformat(),
            deleted=True,
        ),
        headers=headers,
    )

    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": since},
        headers=headers,
    )

    assert response.status_code == 200
    product_in_response = next(
        (p for p in response.json()["products"] if p["id"] == str(product.id)), None
    )
    assert product_in_response is not None
    assert product_in_response.get("deleted_at") is not None

    await db_session.refresh(product)
    assert product.deleted_at is not None


@pytest.mark.asyncio
async def test_sync_changes_server_time_returned(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """La réponse contient server_time proche de now (tolérance 5s)."""
    user = await _create_user(db_session, "sync-changes-srvtime@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    before = datetime.now(UTC)
    response = await client.get("/api/v1/sync/changes", headers=_headers(user.id, store.id))
    after = datetime.now(UTC)

    assert response.status_code == 200
    server_time = datetime.fromisoformat(response.json()["server_time"])
    assert before - timedelta(seconds=5) <= server_time <= after + timedelta(seconds=5)


@pytest.mark.asyncio
async def test_sync_changes_with_pagination(client: AsyncClient, db_session: AsyncSession) -> None:
    """150 produits, limit=100 → 100 items + has_more=True + next_cursor non nul."""
    user = await _create_user(db_session, "sync-changes-paging@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    for i in range(150):
        db_session.add(
            Product(store_id=store.id, name=f"Produit {i:04d}", unit_price=Decimal("1000.00"))
        )
    await db_session.flush()

    since = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": since, "limit": 100},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 100
    assert data["has_more"] is True
    assert data["next_cursor"] is not None


@pytest.mark.asyncio
async def test_sync_changes_use_cursor_to_continue(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Paginer avec next_cursor jusqu'à récupérer les 150 produits complets."""
    user = await _create_user(db_session, "sync-changes-cursor@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    for i in range(150):
        db_session.add(
            Product(
                store_id=store.id,
                name=f"Produit cursor {i:04d}",
                unit_price=Decimal("1000.00"),
            )
        )
    await db_session.flush()

    since = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    headers = _headers(user.id, store.id)
    all_ids: set[str] = set()
    next_cursor: str | None = None
    has_more = True

    while has_more:
        params: dict[str, Any] = {"since": since, "limit": 100}
        if next_cursor:
            params["cursor"] = next_cursor
        r = await client.get("/api/v1/sync/changes", params=params, headers=headers)
        assert r.status_code == 200
        data = r.json()
        for p in data["products"]:
            all_ids.add(p["id"])
        has_more = data["has_more"]
        next_cursor = data.get("next_cursor")

    assert len(all_ids) == 150


@pytest.mark.asyncio
async def test_sync_changes_invalid_limit_zero(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """limit=0 → 422."""
    user = await _create_user(db_session, "sync-changes-lim0@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/sync/changes",
        params={"limit": 0},
        headers=_headers(user.id, store.id),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_changes_invalid_limit_too_high(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """limit=501 → 422."""
    user = await _create_user(db_session, "sync-changes-lim501@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/sync/changes",
        params={"limit": 501},
        headers=_headers(user.id, store.id),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sync_changes_since_without_timezone(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """since sans timezone → 422."""
    user = await _create_user(db_session, "sync-changes-notz@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.get(
        "/api/v1/sync/changes",
        params={"since": "2026-04-30T08:00:00"},  # pas de tz
        headers=_headers(user.id, store.id),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests d'isolation tenant (CRITIQUES)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_sales_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """Vente pushée par A → invisible pour B via GET /sync/changes."""
    user_a = await _create_user(db_session, "iso-sync-a-sale@test.com")
    user_b = await _create_user(db_session, "iso-sync-b-sale@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    sale_id_a = uuid4()
    await client.post(
        "/api/v1/sync/sales",
        json={"sales": [_sale_payload(sale_id=sale_id_a)]},
        headers=_headers(user_a.id, store_a.id),
    )

    response = await client.get("/api/v1/sync/changes", headers=_headers(user_b.id, store_b.id))

    assert response.status_code == 200
    sale_ids_b = [s["id"] for s in response.json()["sales"]]
    assert str(sale_id_a) not in sale_ids_b


@pytest.mark.asyncio
async def test_sync_product_isolation_put(client: AsyncClient, db_session: AsyncSession) -> None:
    """Produit créé par A (UUID propre) → créé avec statut 201, invisible pour B."""
    user_a = await _create_user(db_session, "iso-sync-a-prod@test.com")
    user_b = await _create_user(db_session, "iso-sync-b-prod@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    product_id_a = uuid4()
    r = await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(product_id=product_id_a, name="Produit de A"),
        headers=_headers(user_a.id, store_a.id),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "created"

    # B consulte ses changes → produit de A absent
    response = await client.get("/api/v1/sync/changes", headers=_headers(user_b.id, store_b.id))
    product_ids_b = [p["id"] for p in response.json()["products"]]
    assert str(product_id_a) not in product_ids_b


@pytest.mark.asyncio
async def test_sync_changes_isolation(client: AsyncClient, db_session: AsyncSession) -> None:
    """GET /sync/changes de A ne contient AUCUNE entité de B, et vice-versa."""
    user_a = await _create_user(db_session, "iso-sync-a-changes@test.com")
    user_b = await _create_user(db_session, "iso-sync-b-changes@test.com")
    store_a = await _create_store(db_session, user_a.id, "Store A")
    store_b = await _create_store(db_session, user_b.id, "Store B")
    await db_session.commit()

    headers_a = _headers(user_a.id, store_a.id)
    headers_b = _headers(user_b.id, store_b.id)

    prod_id_a, prod_id_b = uuid4(), uuid4()
    sale_id_a, sale_id_b = uuid4(), uuid4()

    await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(product_id=prod_id_a, name="Produit A"),
        headers=headers_a,
    )
    await client.post(
        "/api/v1/sync/sales",
        json={"sales": [_sale_payload(sale_id=sale_id_a)]},
        headers=headers_a,
    )
    await client.put(
        "/api/v1/sync/products",
        json=_product_sync_payload(product_id=prod_id_b, name="Produit B"),
        headers=headers_b,
    )
    await client.post(
        "/api/v1/sync/sales",
        json={"sales": [_sale_payload(sale_id=sale_id_b)]},
        headers=headers_b,
    )

    r_a = await client.get("/api/v1/sync/changes", headers=headers_a)
    assert r_a.status_code == 200
    data_a = r_a.json()
    prod_ids_a = {p["id"] for p in data_a["products"]}
    sale_ids_a = {s["id"] for s in data_a["sales"]}
    assert str(prod_id_a) in prod_ids_a
    assert str(prod_id_b) not in prod_ids_a
    assert str(sale_id_a) in sale_ids_a
    assert str(sale_id_b) not in sale_ids_a

    r_b = await client.get("/api/v1/sync/changes", headers=headers_b)
    assert r_b.status_code == 200
    data_b = r_b.json()
    prod_ids_b = {p["id"] for p in data_b["products"]}
    sale_ids_b = {s["id"] for s in data_b["sales"]}
    assert str(prod_id_b) in prod_ids_b
    assert str(prod_id_a) not in prod_ids_b
    assert str(sale_id_b) in sale_ids_b
    assert str(sale_id_a) not in sale_ids_b
