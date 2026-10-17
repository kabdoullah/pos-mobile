"""Tests de la suppression de compte DELETE /api/v1/users/me (ADR-0011).

Couvre la purge complète de la boutique (ventes, retours, mouvements, images,
logo), le refus sur mauvais mot de passe, l'isolation entre boutiques et le
maintien de l'immuabilité hors purge.
"""

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token, hash_password
from tests.test_returns import _push_return, _push_sale, _return_payload, _sale_payload, _setup
from tests.test_sync import _headers

_PASSWORD = "motdepasse123"

# Tables portant les données d'une boutique.
_STORE_TABLES = (
    "stock_movements",
    "sale_return_items",
    "sale_returns",
    "sale_items",
    "sales",
    "product_images",
    "products",
    "categories",
    "store_logos",
)


async def _store_with_history(client: AsyncClient, db: AsyncSession, email: str) -> tuple[Any, Any]:
    """Boutique avec vente, retour, mouvements de stock, catégorie, image et logo."""
    # Les requêtes précédentes laissent la session en pos_app (RLS).
    await db.execute(text("RESET ROLE"))
    user, store, product = await _setup(db, email)
    user.password_hash = hash_password(_PASSWORD)
    await db.execute(
        text("INSERT INTO categories (id, store_id, name) VALUES (:id, :sid, 'Boissons')"),
        {"id": str(uuid4()), "sid": str(store.id)},
    )
    await db.execute(
        text(
            "INSERT INTO product_images "
            "(product_id, store_id, content, content_type, width, height, sha256) "
            "VALUES (:pid, :sid, '\\x00', 'image/webp', 1, 1, 'x')"
        ),
        {"pid": str(product.id), "sid": str(store.id)},
    )
    await db.execute(
        text(
            "INSERT INTO store_logos (store_id, content, content_type, width, height, sha256) "
            "VALUES (:sid, '\\x00', 'image/webp', 1, 1, 'x')"
        ),
        {"sid": str(store.id)},
    )
    await db.commit()

    headers = _headers(user.id, store.id)
    line = uuid4()
    sale = _sale_payload([{"id": line, "product_id": product.id, "price": "1000", "quantity": 2}])
    await _push_sale(client, headers, sale)
    await _push_return(
        client, headers, _return_payload(sale["id"], [(line, 1, "resellable", "1000")])
    )
    return user, store


async def _counts(db: AsyncSession, store_id: UUID) -> dict[str, int]:
    """Nombre de lignes par table pour une boutique (hors RLS)."""
    await db.execute(text("RESET ROLE"))
    counts = {}
    for table in _STORE_TABLES:
        counts[table] = (
            await db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE store_id = :sid"), {"sid": str(store_id)}
            )
        ).scalar_one()
    counts["stores"] = (
        await db.execute(
            text("SELECT COUNT(*) FROM stores WHERE id = :sid"), {"sid": str(store_id)}
        )
    ).scalar_one()
    return counts


async def _delete_me(client: AsyncClient, user: Any, store: Any, password: str) -> Any:
    return await client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": password},
        headers=_headers(user.id, store.id),
    )


async def _user_exists(db: AsyncSession, user_id: UUID) -> bool:
    await db.execute(text("RESET ROLE"))
    count = (
        await db.execute(text("SELECT COUNT(*) FROM users WHERE id = :id"), {"id": str(user_id)})
    ).scalar_one()
    return bool(count)


@pytest.mark.asyncio
async def test_delete_account_purges_store_and_user(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store_with_history(client, db_session, "del-all@test.com")
    phone = user.phone_number
    before = await _counts(db_session, store.id)
    assert all(before.values()), before

    response = await _delete_me(client, user, store, _PASSWORD)

    assert response.status_code == 204, response.text
    assert set((await _counts(db_session, store.id)).values()) == {0}
    assert not await _user_exists(db_session, user.id)
    login = await client.post(
        "/api/v1/auth/login", json={"phone_number": phone, "password": _PASSWORD}
    )
    assert login.status_code == 401
    refresh = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": create_refresh_token(user.id)}
    )
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_wrong_password_is_forbidden_and_deletes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user, store = await _store_with_history(client, db_session, "del-wrong@test.com")
    before = await _counts(db_session, store.id)

    response = await _delete_me(client, user, store, "mauvais")

    assert response.status_code == 403
    assert await _counts(db_session, store.id) == before
    assert await _user_exists(db_session, user.id)


@pytest.mark.asyncio
async def test_deleting_one_account_keeps_other_stores_intact(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Isolation : supprimer A ne touche à aucune donnée de B."""
    user_a, store_a = await _store_with_history(client, db_session, "del-iso-a@test.com")
    user_b, store_b = await _store_with_history(client, db_session, "del-iso-b@test.com")
    before_b = await _counts(db_session, store_b.id)

    response = await _delete_me(client, user_a, store_a, _PASSWORD)

    assert response.status_code == 204, response.text
    assert await _counts(db_session, store_b.id) == before_b
    assert await _user_exists(db_session, user_b.id)


@pytest.mark.asyncio
async def test_purge_cannot_delete_a_store_outside_rls_context(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """purge_store est soumise à RLS : une session de A ne purge pas B."""
    _, store_a = await _store_with_history(client, db_session, "del-rls-a@test.com")
    _, store_b = await _store_with_history(client, db_session, "del-rls-b@test.com")
    before_b = await _counts(db_session, store_b.id)

    await db_session.execute(text("SET LOCAL ROLE pos_app"))
    await db_session.execute(text(f"SET LOCAL app.current_store_id = '{store_a.id}'"))
    purge_b = text("SELECT purge_store(:sid)")

    with pytest.raises(DBAPIError, match="not deleted"):
        async with db_session.begin_nested():
            await db_session.execute(purge_b, {"sid": str(store_b.id)})

    assert await _counts(db_session, store_b.id) == before_b


@pytest.mark.asyncio
async def test_sales_stay_immutable_outside_purge(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Hors purge, DELETE et UPDATE restent refusés ; UPDATE même pendant une purge."""
    _, store = await _store_with_history(client, db_session, "del-immutable@test.com")
    await db_session.execute(text("RESET ROLE"))

    for statement in (
        "DELETE FROM sales",
        "DELETE FROM sale_returns",
        "DELETE FROM stock_movements",
        "UPDATE sales SET total_amount = 0",
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            async with db_session.begin_nested():
                await db_session.execute(text(statement))

    await db_session.execute(
        text("SELECT set_config('app.purging_store_id', :sid, true)"), {"sid": str(store.id)}
    )
    with pytest.raises(DBAPIError, match="immutable"):
        async with db_session.begin_nested():
            await db_session.execute(text("UPDATE sales SET total_amount = 0"))
