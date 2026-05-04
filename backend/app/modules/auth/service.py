"""Logique métier du module auth."""
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth import schemas
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository


class AuthService:
    """Service métier de l'authentification."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def register(self, payload: schemas.RegisterRequest) -> User:
        """Crée un nouvel utilisateur après vérification d'unicité de l'email."""
        existing = await self.repo.get_by_email(payload.email)
        if existing is not None:
            raise ConflictError("This email is already registered.", field="email")

        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            phone_number=payload.phone_number,
        )
        await self.repo.create(user)

        # TODO : envoyer email de vérification
        # await EmailService(self.db).send_verification_email(user)

        return user

    async def login(self, payload: schemas.LoginRequest) -> schemas.TokenResponse:
        """Vérifie les credentials et retourne les tokens."""
        user = await self.repo.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            # Message volontairement vague pour ne pas révéler si l'email existe
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is disabled.")

        # TODO : récupérer le store_id associé à l'utilisateur quand le module
        # stores sera implémenté
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

        from uuid import UUID

        user_id = UUID(payload["sub"])
        user = await self.repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or disabled.")

        # TODO : récupérer le store_id
        store_id = None

        return schemas.TokenResponse(
            access_token=create_access_token(user.id, store_id),
            refresh_token=create_refresh_token(user.id),
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    async def send_password_reset(self, email: EmailStr) -> None:
        """Envoie un email de réinitialisation. Silencieux si l'email n'existe pas."""
        user = await self.repo.get_by_email(email)
        if user is None:
            # On ne révèle pas l'existence ou non de l'email
            return

        # TODO : générer un PasswordResetToken et envoyer l'email
        raise NotImplementedError("To be implemented")

    async def reset_password(self, token: str, new_password: str) -> None:
        """Réinitialise le mot de passe via le token."""
        # TODO : valider le token, mettre à jour le password
        raise NotImplementedError("To be implemented")
