"""Tests du service auth — inscription et connexion phone-first."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnauthorizedError
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService


@pytest.mark.asyncio
async def test_register_phone_only(db_session: AsyncSession) -> None:
    """Inscription avec phone seul réussit, email reste None."""
    svc = AuthService(db_session)
    user = await svc.register(RegisterRequest(phone_number="+2250700000001", password="secret123"))
    assert user.phone_number == "+2250700000001"
    assert user.email is None


@pytest.mark.asyncio
async def test_register_phone_and_email(db_session: AsyncSession) -> None:
    """Inscription avec phone + email stocke les deux."""
    svc = AuthService(db_session)
    user = await svc.register(
        RegisterRequest(
            phone_number="+2250700000002",
            password="secret123",
            email="merchant@example.com",
        )
    )
    assert user.phone_number == "+2250700000002"
    assert user.email == "merchant@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_phone_raises_conflict(db_session: AsyncSession) -> None:
    """Deuxième inscription avec même numéro → ConflictError."""
    svc = AuthService(db_session)
    await svc.register(RegisterRequest(phone_number="+2250700000003", password="secret123"))
    with pytest.raises(ConflictError) as exc_info:
        await svc.register(RegisterRequest(phone_number="+2250700000003", password="other_pass"))
    assert exc_info.value.field == "phone_number"


@pytest.mark.asyncio
async def test_register_duplicate_email_raises_conflict(db_session: AsyncSession) -> None:
    """Deux inscriptions avec même email → ConflictError sur le second."""
    svc = AuthService(db_session)
    await svc.register(
        RegisterRequest(
            phone_number="+2250700000004",
            password="secret123",
            email="dup@example.com",
        )
    )
    with pytest.raises(ConflictError) as exc_info:
        await svc.register(
            RegisterRequest(
                phone_number="+2250700000005",
                password="secret123",
                email="dup@example.com",
            )
        )
    assert exc_info.value.field == "email"


@pytest.mark.asyncio
async def test_login_valid_phone(db_session: AsyncSession) -> None:
    """Login avec phone + password correct → TokenResponse."""
    svc = AuthService(db_session)
    await svc.register(RegisterRequest(phone_number="+2250700000006", password="secret123"))
    tokens = await svc.login(LoginRequest(phone_number="+2250700000006", password="secret123"))
    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.token_type == "bearer"


@pytest.mark.asyncio
async def test_login_unknown_phone_raises_unauthorized(db_session: AsyncSession) -> None:
    """Login avec numéro inconnu → UnauthorizedError."""
    svc = AuthService(db_session)
    with pytest.raises(UnauthorizedError):
        await svc.login(LoginRequest(phone_number="+2250700000099", password="secret123"))


@pytest.mark.asyncio
async def test_login_wrong_password_raises_unauthorized(db_session: AsyncSession) -> None:
    """Login avec mauvais mot de passe → UnauthorizedError."""
    svc = AuthService(db_session)
    await svc.register(RegisterRequest(phone_number="+2250700000007", password="secret123"))
    with pytest.raises(UnauthorizedError):
        await svc.login(LoginRequest(phone_number="+2250700000007", password="wrong_pass"))


@pytest.mark.asyncio
async def test_send_password_reset_no_email_is_silent(db_session: AsyncSession) -> None:
    """send_password_reset sur compte sans email → silencieux, pas d'exception."""
    svc = AuthService(db_session)
    await svc.register(RegisterRequest(phone_number="+2250700000008", password="secret123"))
    # Ne doit pas lever d'exception
    await svc.send_password_reset("ghost@example.com")


@pytest.mark.asyncio
async def test_send_password_reset_unknown_email_is_silent(db_session: AsyncSession) -> None:
    """send_password_reset avec email inexistant → silencieux."""
    svc = AuthService(db_session)
    await svc.send_password_reset("nobody@example.com")
