"""Tests d'isolation Row-Level Security entre tenants.

Ces tests vérifient que les politiques RLS PostgreSQL empêchent un tenant
de lire ou modifier les données d'un autre tenant.

CRITIQUE : ces tests doivent passer à chaque modification du schéma.
Si l'un échoue, c'est qu'une faille de sécurité a été introduite.

Voir docs/adr/0002-multi-tenancy-rls.md pour le contexte.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.stores.models import Store


async def _create_user_with_store(db: AsyncSession, email: str) -> tuple[User, Store]:
    """Helper pour créer un user + sa boutique."""
    user = User(
        email=email,
        password_hash="$2b$12$dummy_hash_for_test_only_not_real",
        phone_number="+225 01 02 03 04 05",
    )
    db.add(user)
    await db.flush()

    store = Store(
        owner_id=user.id,
        name=f"Boutique de {email}",
        vat_subject=False,
    )
    db.add(store)
    await db.flush()

    return user, store


async def _set_store_context(db: AsyncSession, store_id) -> None:
    """Switch to non-superuser role + set store_id to enforce RLS.

    pos is a PostgreSQL superuser and bypasses RLS entirely, so we must SET ROLE
    pos_app (a regular role) before any assertion that must respect RLS policies.
    """
    await db.execute(text("SET LOCAL ROLE pos_app"))
    await db.execute(text(f"SET LOCAL app.current_store_id = '{store_id}'"))


async def _reset_store_context(db: AsyncSession) -> None:
    """Revert to superuser pos (bypasses RLS). Use for setup/admin operations."""
    await db.execute(text("RESET ROLE"))
    await db.execute(text("RESET app.current_store_id"))


@pytest.mark.asyncio
async def test_user_a_cannot_read_products_of_user_b(db_session: AsyncSession) -> None:
    """Un user ne doit pas pouvoir lire les produits d'un autre tenant."""
    # Setup : 2 stores avec leurs produits respectifs
    await _reset_store_context(db_session)

    _, store_a = await _create_user_with_store(db_session, "user-a@test.com")
    _, store_b = await _create_user_with_store(db_session, "user-b@test.com")

    product_a = Product(store_id=store_a.id, name="Pain de A", unit_price=Decimal("200.00"))
    product_b = Product(store_id=store_b.id, name="Pain de B", unit_price=Decimal("300.00"))
    db_session.add_all([product_a, product_b])
    await db_session.flush()

    # Activation du contexte tenant A
    await _set_store_context(db_session, store_a.id)

    # User A liste tous les produits : ne doit voir que les siens
    result = await db_session.execute(text("SELECT id, name FROM products"))
    rows = result.fetchall()

    assert len(rows) == 1, "User A doit voir exactement 1 produit (le sien)"
    assert rows[0].name == "Pain de A"

    # User A tente de lire directement le produit de B par son id : invisible
    result = await db_session.execute(
        text("SELECT id FROM products WHERE id = :pid"),
        {"pid": str(product_b.id)},
    )
    assert result.fetchone() is None, "Le produit de B doit être invisible pour A"


@pytest.mark.asyncio
async def test_user_a_cannot_insert_product_for_user_b(db_session: AsyncSession) -> None:
    """Un user ne doit pas pouvoir créer un produit pour un autre tenant."""
    await _reset_store_context(db_session)

    _, store_a = await _create_user_with_store(db_session, "user-a@test.com")
    _, store_b = await _create_user_with_store(db_session, "user-b@test.com")

    # Activation du contexte tenant A
    await _set_store_context(db_session, store_a.id)

    # Tentative d'insertion d'un produit dans la boutique de B : doit échouer
    # à cause de la WITH CHECK clause de la politique RLS
    with pytest.raises(ProgrammingError):
        await db_session.execute(
            text("""
                INSERT INTO products (id, store_id, name, unit_price)
                VALUES (:pid, :sid, 'Pain frauduleux', 100)
            """),
            {"pid": str(uuid4()), "sid": str(store_b.id)},
        )


@pytest.mark.asyncio
async def test_user_a_cannot_update_product_of_user_b(db_session: AsyncSession) -> None:
    """Un user ne doit pas pouvoir modifier un produit d'un autre tenant."""
    await _reset_store_context(db_session)

    _, store_a = await _create_user_with_store(db_session, "user-a@test.com")
    _, store_b = await _create_user_with_store(db_session, "user-b@test.com")

    product_b = Product(store_id=store_b.id, name="Pain de B", unit_price=Decimal("300.00"))
    db_session.add(product_b)
    await db_session.flush()

    # Activation du contexte tenant A
    await _set_store_context(db_session, store_a.id)

    # Tentative d'UPDATE du produit de B : RLS filtre, 0 ligne affectée
    result = await db_session.execute(
        text("UPDATE products SET name = 'Hacked' WHERE id = :pid"),
        {"pid": str(product_b.id)},
    )
    assert result.rowcount == 0, "L'UPDATE de A sur le produit de B ne doit affecter aucune ligne"

    # Vérification que le produit de B est intact
    await _reset_store_context(db_session)
    await _set_store_context(db_session, store_b.id)

    result = await db_session.execute(
        text("SELECT name FROM products WHERE id = :pid"),
        {"pid": str(product_b.id)},
    )
    row = result.fetchone()
    assert row is not None
    assert row.name == "Pain de B", "Le nom du produit de B doit être inchangé"


@pytest.mark.asyncio
async def test_no_store_context_returns_empty(db_session: AsyncSession) -> None:
    """Sans store_id défini dans la session, on ne doit voir aucune ligne tenant."""
    await _reset_store_context(db_session)

    _, store_a = await _create_user_with_store(db_session, "user-a@test.com")
    db_session.add(Product(store_id=store_a.id, name="Pain", unit_price=Decimal("200.00")))
    await db_session.flush()

    # Switch to non-superuser role WITHOUT store_id. RLS evaluates
    # store_id = NULL which is always false → 0 rows visible.
    await _reset_store_context(db_session)
    await db_session.execute(text("SET LOCAL ROLE pos_app"))

    result = await db_session.execute(text("SELECT COUNT(*) FROM products"))
    count = result.scalar()
    assert count == 0, "Sans contexte tenant, RLS doit filtrer 100% des lignes"
