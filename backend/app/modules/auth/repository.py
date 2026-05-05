"""Accès aux données du module auth."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import EmailVerificationToken, PasswordResetToken, User


class UserRepository:
    """Repository pour l'entité User."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Retourne l'utilisateur par son id, ou None."""
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: EmailStr) -> User | None:
        """Retourne l'utilisateur par son email (insensible à la casse)."""
        stmt = select(User).where(User.email == email.lower())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        """Crée un nouvel utilisateur."""
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_password(self, user: User, new_password_hash: str) -> User:
        """Met à jour le mot de passe d'un utilisateur."""
        user.password_hash = new_password_hash
        await self.db.flush()
        return user


class EmailVerificationTokenRepository:
    """Repository pour EmailVerificationToken."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> EmailVerificationToken:
        """Crée et persiste un token de vérification email."""
        token = EmailVerificationToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        """Retourne le token correspondant au hash, ou None."""
        stmt = select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, token: EmailVerificationToken) -> None:
        """Marque le token comme utilisé."""
        token.used_at = datetime.now(UTC)
        await self.db.flush()

    async def invalidate_previous(self, user_id: UUID) -> None:
        """Invalide tous les tokens non utilisés d'un utilisateur avant d'en créer un nouveau."""
        stmt = (
            update(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        await self.db.execute(stmt)


class PasswordResetTokenRepository:
    """Repository pour PasswordResetToken."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, user_id: UUID, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        """Crée et persiste un token de réinitialisation de mot de passe."""
        token = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(token)
        await self.db.flush()
        await self.db.refresh(token)
        return token

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        """Retourne le token correspondant au hash, ou None."""
        stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken) -> None:
        """Marque le token comme utilisé."""
        token.used_at = datetime.now(UTC)
        await self.db.flush()
