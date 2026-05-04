"""Modèles SQLAlchemy du module catalog."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Product(Base):
    """Produit du catalogue d'une boutique.

    Soft delete via deleted_at : un produit supprimé reste en base pour préserver
    l'intégrité des ventes passées qui le référencent.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="chk_products_unit_price_positive"),
        CheckConstraint(
            "current_stock IS NULL OR current_stock >= 0",
            name="chk_products_current_stock_non_negative",
        ),
        CheckConstraint("length(trim(name)) > 0", name="chk_products_name_not_empty"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_products_store"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} price={self.unit_price}>"
