"""Modèles SQLAlchemy du module returns (ADR-0010).

ATTENTION : les tables sale_returns et sale_return_items sont IMMUABLES, comme
sales. Un trigger PostgreSQL refuse les UPDATE/DELETE : une correction passera
par une contrepassation, jamais par une modification.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

RETURN_REASONS = (
    "defective",
    "damaged",
    "wrong_product",
    "sale_error",
    "changed_mind",
    "other",
)
ITEM_CONDITIONS = ("resellable", "damaged", "defective", "unsellable")
REFUND_METHODS = ("cash", "mobile_money_orange", "mobile_money_mtn", "mobile_money_wave")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


class SaleReturn(Base):
    """Retour client d'articles d'une vente. IMMUABLE après création.

    L'id est un UUID v4 généré côté CLIENT (idempotence du sync, comme les ventes).
    Le remboursement est manuel (espèces ou transfert mobile money fait par le
    commerçant) et confirmé au comptoir : refund_amount est ce qui a été rendu.
    """

    __tablename__ = "sale_returns"
    __table_args__ = (
        UniqueConstraint("store_id", "return_number", name="uq_sale_returns_store_return_number"),
        CheckConstraint(_in_list("reason", RETURN_REASONS), name="chk_sale_returns_reason"),
        CheckConstraint(
            "reason != 'other' OR (note IS NOT NULL AND length(trim(note)) > 0)",
            name="chk_sale_returns_other_requires_note",
        ),
        CheckConstraint(
            _in_list("refund_method", REFUND_METHODS), name="chk_sale_returns_refund_method"
        ),
        CheckConstraint("refund_amount >= 0", name="chk_sale_returns_refund_amount_positive"),
    )

    # Pas de default : l'UUID DOIT être fourni par le client.
    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_sale_returns_store"),
        nullable=False,
    )
    sale_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sales.id", ondelete="RESTRICT", name="fk_sale_returns_sale"),
        nullable=False,
    )
    # Rempli par le trigger generate_return_number (BEFORE INSERT).
    return_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    refund_method: Mapped[str] = mapped_column(String(30), nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Horloge CLIENT au moment du retour.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_sale_returns_created_by"),
        nullable=True,
    )
    # Horloge serveur, sert au pull /sync/changes.
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["SaleReturnItem"]] = relationship(
        back_populates="sale_return", cascade="all, delete-orphan", lazy="raise"
    )

    def __repr__(self) -> str:
        return (
            f"<SaleReturn id={self.id} sale_id={self.sale_id} "
            f"number={self.return_number} refund={self.refund_amount}>"
        )


class SaleReturnItem(Base):
    """Ligne d'un retour. Référence la ligne de vente d'origine (jamais le seul produit)."""

    __tablename__ = "sale_return_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_sale_return_items_quantity_positive"),
        CheckConstraint(
            _in_list("condition", ITEM_CONDITIONS), name="chk_sale_return_items_condition"
        ),
        CheckConstraint(
            "NOT restocked OR condition = 'resellable'",
            name="chk_sale_return_items_restocked_resellable",
        ),
        CheckConstraint("refund_amount >= 0", name="chk_sale_return_items_refund_amount_positive"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True)
    sale_return_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sale_returns.id", ondelete="CASCADE", name="fk_sale_return_items_return"),
        nullable=False,
    )
    # Dénormalisé pour le RLS.
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_sale_return_items_store"),
        nullable=False,
    )
    sale_item_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sale_items.id", ondelete="RESTRICT", name="fk_sale_return_items_sale_item"),
        nullable=False,
    )
    # Copie de sale_items.product_id (NULL si le produit a été supprimé).
    product_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL", name="fk_sale_return_items_product"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(String(20), nullable=False)
    # True si l'article a réintégré le stock disponible (revendable, produit actif).
    restocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale_return: Mapped["SaleReturn"] = relationship(back_populates="items", lazy="raise")

    def __repr__(self) -> str:
        return (
            f"<SaleReturnItem id={self.id} sale_item_id={self.sale_item_id} "
            f"qty={self.quantity} condition={self.condition}>"
        )
