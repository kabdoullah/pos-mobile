"""Logique métier du module auth."""

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import EmailService
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth import schemas
from app.modules.auth.models import User
from app.modules.auth.repository import (
    EmailVerificationTokenRepository,
    PasswordResetTokenRepository,
    UserRepository,
)
from app.modules.stores.service import StoreService

logger = structlog.get_logger()


class AuthService:
    """Service métier de l'authentification."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)
        self.email_verification_repo = EmailVerificationTokenRepository(db)
        self.password_reset_repo = PasswordResetTokenRepository(db)
        self.email_service = EmailService()

    async def register(self, payload: schemas.RegisterRequest) -> User:
        """Crée un nouvel utilisateur. Phone requis, email optionnel."""
        existing_phone = await self.repo.get_by_phone(payload.phone_number)
        if existing_phone is not None:
            raise ConflictError("This phone number is already registered.", field="phone_number")

        if payload.email is not None:
            existing_email = await self.repo.get_by_email(payload.email)
            if existing_email is not None:
                raise ConflictError("This email is already registered.", field="email")

        user = User(
            phone_number=payload.phone_number,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        await self.repo.create(user)
        await StoreService(self.db).create_default_for_user(user.id)

        if payload.email is not None:
            raw_token = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
            expires_at = datetime.now(UTC) + timedelta(hours=24)

            await self.email_verification_repo.create(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
            # Best-effort : un échec SMTP ne doit pas bloquer l'inscription.
            try:
                await self.email_service.send_verification_email(
                    to_email=payload.email,
                    user_name=payload.email,
                    raw_token=raw_token,
                )
            except Exception:
                logger.exception("verification_email_send_failed", user_id=str(user.id))

        return user

    async def login(self, payload: schemas.LoginRequest) -> schemas.TokenResponse:
        """Vérifie les credentials et retourne les tokens."""
        phone = payload.phone_number.strip()
        if re.match(r'^0\d{9}$', phone):
            phone = '+225' + phone
        user = await self.repo.get_by_phone(phone)
        if user is None or not verify_password(payload.password, user.password_hash):
            # Message volontairement vague pour ne pas révéler si le numéro existe
            raise UnauthorizedError("Invalid phone number or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is disabled.")

        try:
            store = await StoreService(self.db).get_for_user(user.id)
            store_id = store.id
        except NotFoundError:
            store_id = None

        return schemas.TokenResponse(
            access_token=create_access_token(user.id, store_id),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> schemas.TokenResponse:
        """Renouvelle l'access token à partir d'un refresh valide."""
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token.")

        user_id = UUID(payload["sub"])
        user = await self.repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or disabled.")

        try:
            store = await StoreService(self.db).get_for_user(user.id)
            store_id = store.id
        except NotFoundError:
            store_id = None

        return schemas.TokenResponse(
            access_token=create_access_token(user.id, store_id),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def send_password_reset(self, email: EmailStr) -> None:
        """Envoie un email de réinitialisation. Silencieux si l'email n'existe pas ou n'est pas renseigné."""
        user = await self.repo.get_by_email(email)
        if user is None or user.email is None:
            # Ne révèle ni l'existence du compte ni l'absence d'email
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(UTC) + timedelta(hours=1)

        await self.password_reset_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        # Best-effort : échec SMTP ne doit pas révéler d'info ni renvoyer 500.
        try:
            await self.email_service.send_password_reset_email(
                to_email=user.email,
                user_name=user.email,
                raw_token=raw_token,
            )
        except Exception:
            logger.exception("password_reset_email_send_failed", user_id=str(user.id))

    async def reset_password(self, token: str, new_password: str) -> None:
        """Réinitialise le mot de passe via le token reçu par email."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db_token = await self.password_reset_repo.get_by_hash(token_hash)

        if db_token is None or db_token.used_at is not None:
            raise ValidationError("Invalid or expired token.")

        if db_token.expires_at < datetime.now(UTC):
            raise ValidationError("Invalid or expired token.")

        user = await self.repo.get_by_id(db_token.user_id)
        if user is None:
            raise ValidationError("Invalid or expired token.")

        await self.repo.update_password(user, hash_password(new_password))
        await self.password_reset_repo.mark_used(db_token)
