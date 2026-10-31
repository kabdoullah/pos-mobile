"""Tests d'authentification de l'administrateur plateforme."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient, Response
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_admin_token, decode_admin_token
from app.modules.admin.models import PlatformAdmin
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import AdminLoginRequest
from app.modules.admin.service import AdminService
from app.modules.auth.models import User
from app.modules.stores.models import Store
from tests.factories import ADMIN_EMAIL, ADMIN_PASSWORD, create_admin

LOGIN_URL = "/api/v1/admin/auth/login"
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


@pytest.fixture(autouse=True)
def _admin_secret() -> Iterator[None]:
    with patch.object(settings, "admin_jwt_secret_key", SecretStr("a" * 48)):
        yield


async def _login(client: AsyncClient, password: str, email: str = ADMIN_EMAIL) -> Response:
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_admin(db_session)

    response = await _login(client, ADMIN_PASSWORD, "  Admin@Test.CI ")

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 7200
    payload = decode_admin_token(data["access_token"])
    assert payload is not None
    assert payload["sub"] == str(admin.id)


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_admin(db_session)

    response = await _login(client, "wrong")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_login_unknown_email(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_admin(db_session)

    wrong_pw = await _login(client, "wrong")
    unknown = await _login(client, "wrong", "nobody@test.ci")

    assert unknown.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


@pytest.mark.asyncio
async def test_admin_locked_after_5_failures(client: AsyncClient, db_session: AsyncSession) -> None:
    await create_admin(db_session)

    for _ in range(5):
        assert (await _login(client, "wrong")).status_code == 401
    response = await _login(client, ADMIN_PASSWORD)

    assert response.status_code == 401
    admin = (await db_session.execute(select(PlatformAdmin))).scalar_one()
    await db_session.refresh(admin)
    assert admin.locked_until is not None
    assert admin.locked_until > datetime.now(UTC)


@pytest.mark.asyncio
async def test_admin_unlocked_after_15_minutes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await create_admin(db_session)
    for _ in range(5):
        await _login(client, "wrong")
    await db_session.refresh(admin)
    admin.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await _login(client, ADMIN_PASSWORD)

    assert response.status_code == 200
    await db_session.refresh(admin)
    assert admin.failed_login_count == 0
    assert admin.locked_until is None


@pytest.mark.asyncio
async def test_merchant_token_rejected_on_admin_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(email="m@test.com", password_hash=_DUMMY_HASH, phone_number="+225010101010")
    db_session.add(user)
    await db_session.flush()
    store = Store(owner_id=user.id, name="Boutique")
    db_session.add(store)
    await db_session.commit()

    token = create_access_token(user.id, store.id)
    response = await client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_token_rejected_on_merchant_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_admin(db_session)
    token = (await _login(client, ADMIN_PASSWORD)).json()["access_token"]

    response = await client.get("/api/v1/stores/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_disabled_without_secret(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_admin(db_session)

    with patch.object(settings, "admin_jwt_secret_key", SecretStr("")):
        response = await _login(client, ADMIN_PASSWORD)

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access is not configured."


@pytest.mark.asyncio
async def test_seed_admin_idempotent(db_session: AsyncSession) -> None:
    service = AdminService(db_session)
    await service.ensure_seed_admin(ADMIN_EMAIL, ADMIN_PASSWORD)
    await db_session.commit()
    first_hash = (await db_session.execute(select(PlatformAdmin.password_hash))).scalar_one()

    await service.ensure_seed_admin(ADMIN_EMAIL, "another-password")
    await db_session.commit()

    count = (await db_session.execute(select(func.count()).select_from(PlatformAdmin))).scalar_one()
    assert count == 1
    assert (
        await db_session.execute(select(PlatformAdmin.password_hash))
    ).scalar_one() == first_hash


@pytest.mark.asyncio
async def test_concurrent_failures_lock_account(
    db_session: AsyncSession, db_engine: AsyncEngine
) -> None:
    """Des échecs parallèles (sessions distinctes) ne perdent aucun incrément."""
    admin = await create_admin(db_session)
    maker = async_sessionmaker(db_engine, expire_on_commit=False)

    async def attempt() -> None:
        async with maker() as session:
            with pytest.raises(UnauthorizedError):
                await AdminService(session).login(
                    AdminLoginRequest(email=ADMIN_EMAIL, password="wrong")
                )

    await asyncio.gather(*(attempt() for _ in range(10)))

    await db_session.refresh(admin)
    assert admin.failed_login_count >= 5
    assert admin.locked_until is not None
    assert admin.locked_until > datetime.now(UTC)


@pytest.mark.asyncio
async def test_expired_lock_restarts_counter(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_admin(db_session)
    admin.failed_login_count = 5
    admin.locked_until = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    assert (await _login(client, "wrong")).status_code == 401

    await db_session.refresh(admin)
    assert admin.failed_login_count == 1
    assert admin.locked_until is None


@pytest.mark.asyncio
async def test_valid_admin_token_opens_admin_route(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_admin(db_session)
    token = (await _login(client, ADMIN_PASSWORD)).json()["access_token"]

    response = await client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_deleted_admin_token_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_admin(db_session)
    token = (await _login(client, ADMIN_PASSWORD)).json()["access_token"]
    await db_session.delete(admin)
    await db_session.commit()

    response = await client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_expired_admin_token_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await create_admin(db_session)
    with patch.object(settings, "admin_token_expire_minutes", -1):
        token = create_admin_token(admin.id)

    response = await client.get(
        "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cross_token_rejected_even_with_same_secret(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Audience/type seuls protègent quand les deux clés sont identiques."""
    admin = await create_admin(db_session)
    user = User(email="m2@test.com", password_hash=_DUMMY_HASH, phone_number="+225020202020")
    db_session.add(user)
    await db_session.flush()
    store = Store(owner_id=user.id, name="Boutique")
    db_session.add(store)
    await db_session.commit()

    with patch.object(settings, "admin_jwt_secret_key", settings.jwt_secret_key):
        admin_token = create_admin_token(admin.id)
        merchant_token = create_access_token(user.id, store.id)
        r1 = await client.get(
            "/api/v1/admin/metrics", headers={"Authorization": f"Bearer {merchant_token}"}
        )
        r2 = await client.get(
            "/api/v1/stores/me", headers={"Authorization": f"Bearer {admin_token}"}
        )

    assert r1.status_code == 401
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_failed_login_never_extends_active_lock(db_session: AsyncSession) -> None:
    admin = await create_admin(db_session)
    locked_until = datetime.now(UTC) + timedelta(minutes=5)
    admin.failed_login_count = 5
    admin.locked_until = locked_until
    await db_session.commit()

    await AdminRepository(db_session).register_failed_login(admin.id, 5, 15)
    await db_session.commit()

    await db_session.refresh(admin)
    assert admin.failed_login_count == 5
    assert admin.locked_until == locked_until
