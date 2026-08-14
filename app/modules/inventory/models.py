"""Modèles SQLAlchemy du module inventory.

ATTENTION : la table stock_movements est un ledger APPEND-ONLY et IMMUABLE,
au même titre que sales. Un trigger PostgreSQL refuse les UPDATE/DELETE.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM as PgEnum, UUID as SQLUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Le type ENUM correspondant côté DB est créé dans la migration dédiée.
# create_type=False car le type existe déjà (créé manuellement dans la migration).
stock_movement_reason_type = PgEnum(
    "sale",
    "manual_adjustment",
    "catalog_update",
    name="stock_movement_reason_enum",
    create_type=False,
)


class StockMovement(Base):
    """Ligne d'historique d'une variation de stock produit.

    quantity_delta est nullable : NULL représente la désactivation du tracking
    (current_stock passe à NULL), qui n'est pas un delta numérique. Dans ce cas
    resulting_stock est également NULL (voir CheckConstraint ci-dessous).
    resulting_stock n'a volontairement AUCUNE contrainte de non-négativité :
    une vente ne bloque jamais sur stock insuffisant, le stock peut aller sous zéro.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "quantity_delta IS NOT NULL OR resulting_stock IS NULL",
            name="chk_stock_movements_null_delta_implies_null_resulting_stock",
        ),
        CheckConstraint(
            "(reason = 'sale') = (sale_id IS NOT NULL)",
            name="chk_stock_movements_sale_id_matches_reason",
        ),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_stock_movements_store"),
        nullable=False,
    )
    # RESTRICT (pas SET NULL comme sale_items) : pas de snapshot nom/prix ici,
    # une ligne avec product_id NULL serait inexploitable.
    product_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT", name="fk_stock_movements_product"),
        nullable=False,
    )
    quantity_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(stock_movement_reason_type, nullable=False)
    resulting_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sale_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sales.id", ondelete="SET NULL", name="fk_stock_movements_sale"),
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_stock_movements_created_by"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<StockMovement id={self.id} product_id={self.product_id} "
            f"reason={self.reason} delta={self.quantity_delta}>"
        )
