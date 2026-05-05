"""Modèles SQLAlchemy du module auth."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class User(Base):
    """Utilisateur du système (commerçant). Authentification via email + password."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = LOWER(email)", name="chk_users_email_lowercase"),
        CheckConstraint(
            r"email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'",
            name="chk_users_email_format",
        ),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class EmailVerificationToken(Base):
    """Token de vérification email à usage unique."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_email_verification_tokens_user"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PasswordResetToken(Base):
    """Token de réinitialisation de mot de passe à usage unique."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_password_reset_tokens_user"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
