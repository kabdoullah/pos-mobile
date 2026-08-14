"""Modèles SQLAlchemy du module stores."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Store(Base):
    """Boutique du commerçant. Pivot du multi-tenancy.

    Au MVP, exactement une boutique par utilisateur (contrainte unique sur owner_id).
    """

    __tablename__ = "stores"

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_stores_owner"),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    ncc: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vat_subject: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    receipt_footer_text: Mapped[str | None] = mapped_column(String(200), nullable=True)

    next_receipt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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
        return f"<Store id={self.id} name={self.name!r}>"
