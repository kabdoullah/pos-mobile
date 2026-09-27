"""Tests des reçus enrichis (ADR-0008) : téléphone boutique, profil vendeur,
vendeur de la vente et reçu PDF (logo, téléphone, « Vendeur : … »)."""

import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.sales.models import Sale
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


async def _store(db: AsyncSession, email: str) -> tuple[User, Store]:
    user = User(
        email=email, password_hash=_DUMMY_HASH, phone_number=f"+225{abs(hash(email)) % 10**9:09d}"
    )
    db.add(user)
    await db.flush()
    store = Store(owner_id=user.id, name="Boutique Awa")
    db.add(store)
    await db.flush()
    await db.commit()
    return user, store


def _headers(user: User, store: Store) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, store.id)}"}


def _sale_payload(sale_id: UUID) -> dict[str, Any]:
    return {
        "id": str(sale_id),
        "items": [
            {
                "product_id": None,
                "product_name_at_sale": "Baguette",
                "unit_price_at_sale": "250.00",
                "quantity": 2,
                "line_total": "500.00",
            }
        ],
        "total_amount": "500.00",
        "vat_amount": "0.00",
        "payment_method": "cash",
        "cash_amount": None,
        "mobile_money_amount": None,
        "created_at": datetime.now(UTC).isoformat(),
    }


async def _sync_sale(client: AsyncClient, headers: dict[str, str]) -> UUID:
    sale_id = uuid4()
    r = await client.post(
        "/api/v1/sync/sales", json={"sales": [_sale_payload(sale_id)]}, headers=headers
    )
    assert r.status_code == 200
    return sale_id


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (300, 100), (10, 10, 10)).save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Téléphone de la boutique
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_phone_set_validated_and_cleared(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "rcpt-phone@test.com")
    headers = _headers(user, store)

    r = await client.patch("/api/v1/stores/me", json={"phone": "+2250700000000"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["phone"] == "+2250700000000"

    r = await client.patch("/api/v1/stores/me", json={"phone": "0700000000"}, headers=headers)
    assert r.status_code == 422

    r = await client.patch("/api/v1/stores/me", json={"phone": None}, headers=headers)
    assert r.json()["phone"] is None


# ---------------------------------------------------------------------------
# Profil /api/v1/users/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_users_me_display_name(client: AsyncClient, db_session: AsyncSession) -> None:
    user, store = await _store(db_session, "rcpt-me@test.com")
    headers = _headers(user, store)

    r = await client.get("/api/v1/users/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["phone_number"] == user.phone_number
    assert r.json()["display_name"] is None

    r = await client.patch("/api/v1/users/me", json={"display_name": "  Awa  "}, headers=headers)
    assert r.json()["display_name"] == "Awa"

    # Champ absent : inchangé.
    r = await client.patch("/api/v1/users/me", json={}, headers=headers)
    assert r.json()["display_name"] == "Awa"

    # Vide : retiré du reçu.
    r = await client.patch("/api/v1/users/me", json={"display_name": "   "}, headers=headers)
    assert r.json()["display_name"] is None

    r = await client.patch("/api/v1/users/me", json={"display_name": "x" * 81}, headers=headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_users_me_requires_authentication(client: AsyncClient) -> None:
    r = await client.get("/api/v1/users/me")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Vendeur de la vente
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synced_sale_records_its_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "rcpt-seller@test.com")
    sale_id = await _sync_sale(client, _headers(user, store))

    sale = (await db_session.execute(select(Sale).where(Sale.id == sale_id))).scalar_one()
    assert sale.created_by == user.id


# ---------------------------------------------------------------------------
# Reçu PDF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receipt_pdf_shows_logo_phone_and_seller(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store(db_session, "rcpt-pdf-full@test.com")
    headers = _headers(user, store)
    await client.patch("/api/v1/stores/me", json={"phone": "+2250700000000"}, headers=headers)
    await client.patch("/api/v1/users/me", json={"display_name": "Awa"}, headers=headers)
    await client.put("/api/v1/stores/me/logo", files={"file": ("l.png", _png())}, headers=headers)
    sale_id = await _sync_sale(client, headers)

    r = await client.get(f"/api/v1/sales/{sale_id}/receipt", headers=headers)
    assert r.status_code == 200
    pdf = r.content
    assert pdf.startswith(b"%PDF")
    assert b"+2250700000000" in pdf
    assert b"Vendeur : Awa" in pdf
    assert b"/Subtype /Image" in pdf


@pytest.mark.asyncio
async def test_receipt_pdf_without_optional_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Sans logo, téléphone ni nom de vendeur : reçu identique à avant."""
    user, store = await _store(db_session, "rcpt-pdf-min@test.com")
    headers = _headers(user, store)
    sale_id = await _sync_sale(client, headers)

    pdf = (await client.get(f"/api/v1/sales/{sale_id}/receipt", headers=headers)).content
    assert pdf.startswith(b"%PDF")
    assert b"Vendeur" not in pdf
    assert b"/Subtype /Image" not in pdf
