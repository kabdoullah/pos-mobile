"""Tests d'authentification de l'administrateur plateforme."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, decode_admin_token
from app.modules.admin.models import PlatformAdmin
from app.modules.admin.service import AdminService
from app.modules.auth.models import User
from app.modules.stores.models import Store

ADMIN_EMAIL = "admin@test.ci"
ADMIN_PASSWORD = "S3cret-pass!"
LOGIN_URL = "/api/v1/admin/auth/login"
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdGhhc2g"


@pytest.fixture(autouse=True)
def _admin_secret() -> Iterator[None]:
    with patch.object(settings, "admin_jwt_secret_key", SecretStr("a" * 48)):
        yield


async def _create_admin(db: AsyncSession) -> PlatformAdmin:
    await AdminService(db).ensure_seed_admin(ADMIN_EMAIL, ADMIN_PASSWORD)
    await db.commit()
    return (await db.execute(select(PlatformAdmin))).scalar_one()


async def _login(client: AsyncClient, password: str, email: str = ADMIN_EMAIL):  # type: ignore[no-untyped-def]
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _create_admin(db_session)

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
    await _create_admin(db_session)

    response = await _login(client, "wrong")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_admin_login_unknown_email(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_admin(db_session)

    wrong_pw = await _login(client, "wrong")
    unknown = await _login(client, "wrong", "nobody@test.ci")

    assert unknown.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


@pytest.mark.asyncio
async def test_admin_locked_after_5_failures(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_admin(db_session)

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
    admin = await _create_admin(db_session)
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
    await _create_admin(db_session)
    token = (await _login(client, ADMIN_PASSWORD)).json()["access_token"]

    response = await client.get("/api/v1/stores/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_disabled_without_secret(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create_admin(db_session)

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
