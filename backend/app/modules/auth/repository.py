"""Accès aux données du module auth."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import EmailStr

from app.modules.auth.models import User


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
