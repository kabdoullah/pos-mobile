"""Script de seed : crée un compte de test avec une boutique et quelques produits.

Usage :
    cd backend
    uv run python scripts/seed_test_data.py

Crée :
- 1 utilisateur : test@gmail.com / password : TestPassword123
- 1 boutique : "Boutique Test"
- 5 produits avec codes-barres
- 0 vente (à créer via l'API ou via le mobile)

À NE PAS UTILISER EN PRODUCTION. Le script vérifie l'environnement avant de tourner.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

# Ajout de app/ au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.modules.auth.models import User  # noqa: E402
from app.modules.catalog.models import Product  # noqa: E402
from app.modules.stores.models import Store  # noqa: E402

TEST_EMAIL = "test@gmail.com"
TEST_PASSWORD = "TestPassword123"

PRODUCTS_TO_CREATE = [
    {"name": "Pain de mie", "barcode": "3017620422003", "unit_price": "500.00", "stock": 50},
    {"name": "Eau minérale 1.5L", "barcode": "3068320055000", "unit_price": "300.00", "stock": 100},
    {"name": "Café Nescafé sachet", "barcode": "7613032567736", "unit_price": "150.00", "stock": 200},
    {"name": "Savon de Marseille", "barcode": "3245676543210", "unit_price": "750.00", "stock": 30},
    {"name": "Banane (kg)", "barcode": None, "unit_price": "400.00", "stock": None},
]


async def seed() -> None:
    """Crée les données de test."""
    if settings.environment == "production":
        print("❌ Ce script ne doit pas être lancé en production. Abandon.")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        # Vérifier que le user n'existe pas déjà
        from sqlalchemy import select

        existing = await session.execute(
            select(User).where(User.email == TEST_EMAIL)
        )
        if existing.scalar_one_or_none() is not None:
            print(f"❌ L'utilisateur {TEST_EMAIL} existe déjà. Abandon.")
            print("   Pour repartir de zéro : DELETE manuellement ou drop+migrate.")
            sys.exit(1)

        # 1. Créer l'utilisateur
        user = User(
            email=TEST_EMAIL,
            password_hash=hash_password(TEST_PASSWORD),
            phone_number="+225 01 02 03 04 05",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        print(f"✅ Utilisateur créé : {user.email}")

        # 2. Créer la boutique
        store = Store(
            owner_id=user.id,
            name="Boutique Test",
            address="Adjamé, Abidjan",
            ncc="1234567",
            vat_subject=False,
            receipt_footer_text="Merci de votre visite !",
        )
        session.add(store)
        await session.flush()
        print(f"✅ Boutique créée : {store.name}")

        # 3. Créer les produits
        for p in PRODUCTS_TO_CREATE:
            product = Product(
                store_id=store.id,
                name=p["name"],
                barcode=p["barcode"],
                unit_price=Decimal(p["unit_price"]),
                current_stock=p["stock"],
            )
            session.add(product)

        await session.commit()
        print(f"✅ {len(PRODUCTS_TO_CREATE)} produits créés")
        print()
        print("=" * 60)
        print("Setup terminé. Identifiants de test :")
        print(f"  Email    : {TEST_EMAIL}")
        print(f"  Password : {TEST_PASSWORD}")
        print(f"  Store ID : {store.id}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
