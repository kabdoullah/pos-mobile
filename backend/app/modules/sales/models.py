"""Modèles SQLAlchemy du module sales.

ATTENTION : la table sales est IMMUABLE. Aucun UPDATE/DELETE ne doit être effectué
sur les instances après leur création initiale. Un trigger PostgreSQL refuse les
modifications, en plus de la discipline applicative.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


# Le type ENUM correspondant côté DB est créé dans la migration 0001_initial_schema.
# create_type=False car le type existe déjà (créé manuellement dans la migration).
payment_method_type = PgEnum(
    "cash",
    "mobile_money_orange",
    "mobile_money_mtn",
    "mobile_money_wave",
    "mixed",
    name="payment_method_enum",
    create_type=False,
)


class Sale(Base):
    """Vente encaissée. IMMUABLE après création.

    L'id est un UUID v4 généré côté CLIENT (pas serveur) pour garantir
    l'idempotence du sync : un retry après timeout ne crée pas de doublon
    grâce au INSERT ON CONFLICT DO NOTHING.
    """

    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("store_id", "receipt_number", name="uq_sales_store_receipt_number"),
        CheckConstraint(
            "total_amount >= 0 AND vat_amount >= 0",
            name="chk_sales_amounts_positive",
        ),
        CheckConstraint("vat_amount <= total_amount", name="chk_sales_vat_lte_total"),
        CheckConstraint(
            "(payment_method = 'mixed' AND cash_amount IS NOT NULL AND mobile_money_amount IS NOT NULL) "
            "OR (payment_method != 'mixed' AND (cash_amount IS NULL OR mobile_money_amount IS NULL))",
            name="chk_sales_mixed_amounts",
        ),
        CheckConstraint(
            "payment_method != 'mixed' "
            "OR (COALESCE(cash_amount, 0) + COALESCE(mobile_money_amount, 0) = total_amount)",
            name="chk_sales_mixed_sum_equals_total",
        ),
    )

    # Pas de default=uuid4 ici : l'UUID DOIT être fourni par le client
    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True)

    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_sales_store"),
        nullable=False,
    )

    # receipt_number nullable côté ORM car le trigger PostgreSQL le remplit
    # automatiquement BEFORE INSERT. Côté code applicatif, après commit,
    # il sera toujours défini.
    receipt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    payment_method: Mapped[str] = mapped_column(payment_method_type, nullable=False)

    cash_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    mobile_money_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    # Pas de server_default : c'est le timestamp côté CLIENT au moment de la vente
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Sale id={self.id} receipt_number={self.receipt_number} total={self.total_amount}>"


class SaleItem(Base):
    """Ligne individuelle d'une vente.

    Le nom et le prix du produit sont COPIÉS au moment de la vente
    (product_name_at_sale, unit_price_at_sale) pour préserver l'intégrité
    de l'historique même si le produit est ensuite modifié ou supprimé.
    """

    __tablename__ = "sale_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_sale_items_quantity_positive"),
        CheckConstraint(
            "unit_price_at_sale >= 0",
            name="chk_sale_items_unit_price_positive",
        ),
        CheckConstraint(
            "line_total = unit_price_at_sale * quantity",
            name="chk_sale_items_line_total",
        ),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    sale_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("sales.id", ondelete="CASCADE", name="fk_sale_items_sale"),
        nullable=False,
    )
    # Dénormalisé pour le RLS efficient
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_sale_items_store"),
        nullable=False,
    )
    # Nullable : si le produit a été hard-deleted (rare), product_id passe à NULL
    # mais product_name_at_sale et unit_price_at_sale restent intacts
    product_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL", name="fk_sale_items_product"),
        nullable=True,
    )

    product_name_at_sale: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price_at_sale: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<SaleItem id={self.id} product={self.product_name_at_sale!r} "
            f"qty={self.quantity} total={self.line_total}>"
        )
