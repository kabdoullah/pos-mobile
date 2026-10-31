"""Helpers partagés des tests (utilisateurs, boutiques, ventes, en-têtes, admin)."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.modules.admin.models import PlatformAdmin
from app.modules.admin.service import AdminService
from app.modules.auth.models import User
from app.modules.sales.models import Sale
from app.modules.stores.models import Store

DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"
ADMIN_EMAIL = "admin@test.ci"
ADMIN_PASSWORD = "S3cret-pass!"


async def create_user(db: AsyncSession, email: str) -> User:
    """Crée un utilisateur (téléphone dérivé de l'email)."""
    user = User(
        email=email,
        password_hash=DUMMY_HASH,
        phone_number=f"+225{abs(hash(email)) % 10**9:09d}",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def create_store(db: AsyncSession, owner_id: UUID, name: str = "Ma boutique") -> Store:
    """Crée une boutique pour un propriétaire."""
    store = Store(owner_id=owner_id, name=name)
    db.add(store)
    await db.flush()
    await db.refresh(store)
    return store


async def create_user_with_store(db: AsyncSession, email: str) -> tuple[User, Store]:
    """Crée un utilisateur et sa boutique."""
    user = await create_user(db, email)
    return user, await create_store(db, user.id, f"Boutique de {email}")


async def create_numbered_store(
    db: AsyncSession,
    n: int,
    created_at: datetime | None = None,
    suspended: bool = False,
    name: str | None = None,
) -> tuple[User, Store]:
    """Crée un propriétaire et une boutique numérotés (données déterministes)."""
    user = User(email=f"s{n}@test.com", password_hash=DUMMY_HASH, phone_number=f"+2250700{n:05d}")
    db.add(user)
    await db.flush()
    store = Store(
        owner_id=user.id,
        name=name or f"Boutique {n}",
        created_at=created_at or datetime.now(UTC),
        suspended_at=datetime.now(UTC) if suspended else None,
    )
    db.add(store)
    await db.flush()
    return user, store


def make_sale(store: Store, amount: str, created_at: datetime) -> Sale:
    """Construit une vente espèces (non ajoutée à la session)."""
    return Sale(
        id=uuid4(),
        store_id=store.id,
        total_amount=Decimal(amount),
        payment_method="cash",
        cash_amount=Decimal(amount),
        created_at=created_at,
    )


def auth_headers(user_id: UUID, store_id: UUID) -> dict[str, str]:
    """En-tête Bearer d'un commerçant."""
    return {"Authorization": f"Bearer {create_access_token(user_id, store_id)}"}


async def create_admin(db: AsyncSession) -> PlatformAdmin:
    """Crée (et commit) l'admin plateforme de test."""
    await AdminService(db).ensure_seed_admin(ADMIN_EMAIL, ADMIN_PASSWORD)
    await db.commit()
    return (await db.execute(select(PlatformAdmin))).scalar_one()
