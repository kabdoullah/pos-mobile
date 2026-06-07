"""Seeder de démarrage : crée le compte super admin si configuré."""

import structlog

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.exceptions import ConflictError
from app.modules.auth.schemas import RegisterRequest
from app.modules.auth.service import AuthService

logger = structlog.get_logger()


async def seed_superadmin() -> None:
    """Crée le compte super admin au démarrage si SUPERADMIN_PHONE est défini.

    Idempotent : si le numéro existe déjà, ne fait rien.
    Skippé silencieusement si SUPERADMIN_PHONE ou SUPERADMIN_PASSWORD sont absents.
    """
    phone = settings.superadmin_phone.strip()
    password = settings.superadmin_password.get_secret_value().strip()

    if not phone or not password:
        return

    email: str | None = settings.superadmin_email.strip() or None

    async with AsyncSessionLocal() as session:
        try:
            user = await AuthService(session).register(
                RegisterRequest(
                    phone_number=phone,
                    password=password,
                    email=email,
                )
            )
            await session.commit()
            logger.info("superadmin_created", phone=phone, user_id=str(user.id))
        except ConflictError:
            logger.info("superadmin_already_exists", phone=phone)
