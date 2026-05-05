"""Tests d'intégration du module stores."""

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.auth.models import User
from app.modules.stores.models import Store

_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


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


def _headers(user_id: UUID, store_id: UUID | None = None) -> dict[str, str]:
    token = create_access_token(user_id, store_id)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /api/v1/stores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_store_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """User sans boutique → POST /stores → 201 avec store créé."""
    user = await _create_user(db_session, "no-store@test.com")
    await db_session.commit()

    response = await client.post(
        "/api/v1/stores",
        json={"name": "Épicerie du coin"},
        headers=_headers(user.id),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Épicerie du coin"
    assert data["owner_id"] == str(user.id)
    assert data["vat_subject"] is False


@pytest.mark.asyncio
async def test_create_store_already_exists(client: AsyncClient, db_session: AsyncSession) -> None:
    """User avec boutique existante → POST /stores → 409."""
    user = await _create_user(db_session, "has-store@test.com")
    await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.post(
        "/api/v1/stores",
        json={"name": "Deuxième boutique"},
        headers=_headers(user.id),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_store_unauthenticated(client: AsyncClient) -> None:
    """Pas de JWT → POST /stores → 401."""
    response = await client.post("/api/v1/stores", json={"name": "Test"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/stores/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_my_store_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """User avec boutique → GET /stores/me → 200 avec les bonnes infos."""
    user = await _create_user(db_session, "get-store@test.com")
    store = await _create_store(db_session, user.id, "Boutique test")
    await db_session.commit()

    response = await client.get(
        "/api/v1/stores/me",
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(store.id)
    assert data["name"] == "Boutique test"
    assert data["owner_id"] == str(user.id)


@pytest.mark.asyncio
async def test_get_my_store_no_store(client: AsyncClient, db_session: AsyncSession) -> None:
    """JWT sans store_id → GET /stores/me → 401 (Store context required)."""
    user = await _create_user(db_session, "no-jwt-store@test.com")
    await db_session.commit()

    response = await client.get(
        "/api/v1/stores/me",
        headers=_headers(user.id, store_id=None),
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/v1/stores/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_my_store_partial(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH avec seulement le name → seul le name est modifié."""
    user = await _create_user(db_session, "patch-store@test.com")
    store = await _create_store(db_session, user.id, "Nom initial")
    await db_session.commit()

    response = await client.patch(
        "/api/v1/stores/me",
        json={"name": "Nouveau nom"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nouveau nom"
    assert data["vat_subject"] is False
    assert data["address"] is None


@pytest.mark.asyncio
async def test_update_my_store_invalid_ncc(client: AsyncClient, db_session: AsyncSession) -> None:
    """PATCH avec ncc de 5 caractères → 422 (validation Pydantic)."""
    user = await _create_user(db_session, "ncc-invalid@test.com")
    store = await _create_store(db_session, user.id)
    await db_session.commit()

    response = await client.patch(
        "/api/v1/stores/me",
        json={"ncc": "12345"},
        headers=_headers(user.id, store.id),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Bonus : isolation RLS (accès DB direct — le client test utilise pos superuser
# qui bypass RLS, donc on teste la politique directement comme test_rls_isolation.py)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rls_store_a_invisible_in_context_of_store_b(db_session: AsyncSession) -> None:
    """Avec contexte RLS = store_b, la boutique A est invisible.

    La politique RLS sur stores : id = current_setting('app.current_store_id').
    Si on set le contexte à store_b, seul store_b est visible.
    """
    # Reset to superuser for setup
    await db_session.execute(text("RESET ROLE"))

    user_a = await _create_user(db_session, "rls-store-a@test.com")
    user_b = await _create_user(db_session, "rls-store-b@test.com")
    store_a = await _create_store(db_session, user_a.id, "Boutique A")
    store_b = await _create_store(db_session, user_b.id, "Boutique B")
    await db_session.flush()

    # Activer RLS avec contexte = store_b (non-superuser obligatoire)
    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_b.id}'"))

    # Lister toutes les boutiques : seule store_b visible
    result = await db_session.execute(text("SELECT id FROM stores"))
    visible_ids = {row.id for row in result.fetchall()}

    assert store_b.id in visible_ids, "store_b doit être visible dans son propre contexte"
    assert store_a.id not in visible_ids, "store_a doit être invisible dans le contexte de store_b"
