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
from app.core.email import EmailService, password_reset_link
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    StoreSuspendedError,
    UnauthorizedError,
    ValidationError,
)
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


def normalize_login_phone(phone_number: str) -> str:
    """Numéro tel que recherché en base au login (`07…` → `+22507…`).

    Sert aussi de clé de rate limiting : une même clé ⇔ un même compte visé.
    """
    phone = phone_number.strip()
    if re.match(r"^0\d{9}$", phone):
        phone = "+225" + phone
    return phone


_PASSWORD_RESET_TTL = timedelta(hours=1)


async def _issue_password_reset_token(
    repo: PasswordResetTokenRepository, user_id: UUID
) -> tuple[str, datetime]:
    """Crée un token de reset (1h, usage unique, stocké hashé) ; retourne le token brut.

    Les tokens précédents non utilisés sont invalidés : un seul lien valide à la fois.
    """
    await repo.invalidate_unused(user_id)
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + _PASSWORD_RESET_TTL
    await repo.create(
        user_id=user_id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=expires_at,
    )
    return raw_token, expires_at


class AuthService:
    """Service métier de l'authentification."""

    def __init__(self, db: AsyncSession, email_service: EmailService) -> None:
        self.db = db
        self.repo = UserRepository(db)
        self.email_verification_repo = EmailVerificationTokenRepository(db)
        self.password_reset_repo = PasswordResetTokenRepository(db)
        self.email_service = email_service

    async def register(self, payload: schemas.RegisterRequest) -> User:
        """Crée un nouvel utilisateur. Phone et email requis."""
        existing_phone = await self.repo.get_by_phone(payload.phone_number)
        if existing_phone is not None:
            raise ConflictError("This phone number is already registered.", field="phone_number")

        if await self.repo.get_by_email(payload.email) is not None:
            raise ConflictError("This email is already registered.", field="email")

        user = User(
            phone_number=payload.phone_number,
            email=payload.email,
            password_hash=hash_password(payload.password),
        )
        await self.repo.create(user)
        await StoreService(self.db).create_default_for_user(user.id)

        await self._send_verification(user.id, payload.email)
        return user

    async def _send_verification(self, user_id: UUID, email: str) -> None:
        """Émet un token de vérification (24h) et l'envoie par email.

        Les tokens précédents non utilisés sont invalidés : seul le dernier lien marche.
        """
        raw_token = secrets.token_urlsafe(32)
        await self.email_verification_repo.invalidate_previous(user_id)
        await self.email_verification_repo.create(
            user_id=user_id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        # Best-effort : un échec d'envoi ne doit pas faire échouer la requête.
        try:
            await self.email_service.send_verification_email(
                to_email=email,
                user_name=email,
                raw_token=raw_token,
            )
        except Exception:
            logger.exception("verification_email_send_failed", user_id=str(user_id))

    async def resend_verification(self, user_id: UUID) -> None:
        """Renvoie le lien de vérification. Sans effet si l'email est déjà vérifié."""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.email is None:
            raise ValidationError("No email address on this account.", field="email")
        if user.email_verified_at is not None:
            return
        await self._send_verification(user.id, user.email)

    async def update_email(self, user_id: UUID, email: str, password: str) -> User:
        """Ajoute un email au compte, ou corrige un email pas encore vérifié.

        Mot de passe revérifié (403 s'il est faux, comme delete_me) : une session
        ouverte ne suffit pas à détourner la récupération du compte. Un email
        vérifié ne peut pas être remplacé ici (il faudrait prévenir l'ancienne
        adresse). Envoie le lien de vérification à la nouvelle adresse.
        """
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not verify_password(password, user.password_hash):
            raise ForbiddenError("Invalid password.")
        if user.email_verified_at is not None:
            raise ConflictError("A verified email cannot be changed.", field="email")
        if user.email != email:
            if await self.repo.get_by_email(email) is not None:
                raise ConflictError("This email is already registered.", field="email")
            user = await self.repo.update_email(user, email)
            logger.info("account_email_updated", user_id=str(user.id))
        await self._send_verification(user.id, email)
        return user

    async def verify_email(self, token: str) -> None:
        """Confirme l'adresse email via le token reçu par email."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        db_token = await self.email_verification_repo.get_by_hash(token_hash)

        if db_token is None or db_token.used_at is not None:
            raise ValidationError("Invalid or expired token.")
        if db_token.expires_at < datetime.now(UTC):
            raise ValidationError("Invalid or expired token.")

        user = await self.repo.get_by_id(db_token.user_id)
        if user is None:
            raise ValidationError("Invalid or expired token.")

        if user.email_verified_at is None:
            await self.repo.mark_email_verified(user)
        await self.email_verification_repo.mark_used(db_token)

    async def _active_store_id(self, user_id: UUID) -> UUID | None:
        """Id de la boutique de l'utilisateur (None sans boutique) ; refuse si suspendue."""
        try:
            store = await StoreService(self.db).get_for_user(user_id)
        except NotFoundError:
            store = None
        if store is not None and store.suspended_at is not None:
            raise StoreSuspendedError
        return store.id if store is not None else None

    async def login(self, payload: schemas.LoginRequest) -> schemas.TokenResponse:
        """Vérifie les credentials et retourne les tokens."""
        user = await self.repo.get_by_phone(normalize_login_phone(payload.phone_number))
        if user is None or not verify_password(payload.password, user.password_hash):
            # Message volontairement vague pour ne pas révéler si le numéro existe
            raise UnauthorizedError("Invalid phone number or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is disabled.")

        store_id = await self._active_store_id(user.id)

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

        store_id = await self._active_store_id(user.id)

        return schemas.TokenResponse(
            access_token=create_access_token(user.id, store_id),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def send_password_reset(self, email: EmailStr) -> None:
        """Envoie un email de réinitialisation, uniquement vers une adresse vérifiée.

        Silencieux si le compte n'existe pas ou si son email n'est pas vérifié :
        sinon, quiconque inscrit avec l'email d'autrui pourrait en recevoir les liens.
        """
        user = await self.repo.get_by_email(email)
        if user is None or user.email is None or user.email_verified_at is None:
            # Ne révèle ni l'existence du compte ni l'état de vérification
            return

        raw_token, _ = await _issue_password_reset_token(self.password_reset_repo, user.id)
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
        user_id = await self.password_reset_repo.consume(token_hash)
        user = await self.repo.get_by_id(user_id) if user_id is not None else None
        if user is None:
            raise ValidationError("Invalid or expired token.")

        await self.repo.update_password(user, hash_password(new_password))
        # Les autres liens encore valides (email, support) ne doivent plus servir.
        await self.password_reset_repo.invalidate_unused(user.id)


class UserService:
    """Profil de l'utilisateur connecté (nom affiché sur les reçus, ADR-0008)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def get_me(self, user_id: UUID) -> User:
        """Utilisateur connecté, ou NotFoundError."""
        user = await self.repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def update_me(self, user_id: UUID, payload: schemas.UserMeUpdate) -> User:
        """Met à jour le profil (champs fournis uniquement)."""
        user = await self.get_me(user_id)
        if "display_name" in payload.model_fields_set:
            user = await self.repo.update_display_name(user, payload.display_name)
        return user

    async def delete_me(self, user_id: UUID, password: str) -> None:
        """Supprime définitivement le compte, sa boutique et toutes ses données (ADR-0011).

        Mauvais mot de passe : ForbiddenError (403) et non 401, qui ferait
        rafraîchir le token par l'app au lieu d'afficher l'erreur.
        """
        user = await self.get_me(user_id)
        if not verify_password(password, user.password_hash):
            raise ForbiddenError("Invalid password.")
        await StoreService(self.db).purge_for_user(user.id)
        await self.repo.delete(user)
        logger.info("account_deleted", user_id=str(user_id))

    async def issue_password_reset_link(self, user_id: UUID) -> tuple[User, str, datetime]:
        """Lien de reset remis par le support (ADR-0014), quel que soit l'état de l'email.

        Retourne (utilisateur, lien, expiration). Le lien n'est jamais journalisé.
        """
        user = await self.get_me(user_id)
        if not user.is_active:
            raise ConflictError("User account is inactive.")
        raw_token, expires_at = await _issue_password_reset_token(
            PasswordResetTokenRepository(self.db), user.id
        )
        return user, password_reset_link(raw_token), expires_at

    async def get_display_name(self, user_id: UUID | None) -> str | None:
        """Nom affiché d'un utilisateur (reçu), ou None s'il n'est pas renseigné."""
        if user_id is None:
            return None
        user = await self.repo.get_by_id(user_id)
        return user.display_name if user is not None else None
