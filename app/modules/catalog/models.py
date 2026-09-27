"""Modèles SQLAlchemy du module catalog."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Category(Base):
    """Catégorie de produits d'une boutique (ADR-0008).

    Synchronisée par état comme le catalogue (last-write-wins, id généré par le
    client). Soft delete via deleted_at ; la suppression détache ses produits.
    Nom unique par boutique, insensible à la casse, parmi les non supprimées
    (index unique partiel en migration).
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="chk_categories_name_not_empty"),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_categories_store"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r}>"


class Product(Base):
    """Produit du catalogue d'une boutique.

    Soft delete via deleted_at : un produit supprimé reste en base pour préserver
    l'intégrité des ventes passées qui le référencent.
    """

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("selling_price >= 0", name="chk_products_selling_price_positive"),
        CheckConstraint(
            "purchase_price IS NULL OR purchase_price >= 0",
            name="chk_products_purchase_price_positive",
        ),
        CheckConstraint("length(trim(name)) > 0", name="chk_products_name_not_empty"),
        CheckConstraint(
            "min_stock IS NULL OR min_stock >= 0", name="chk_products_min_stock_non_negative"
        ),
    )

    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_products_store"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Prix de vente normal (ADR-0009, ex-unit_price).
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # Prix d'achat (coût d'acquisition) ; NULL = non renseigné. Donnée interne.
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    current_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL", name="fk_products_category"),
        nullable=True,
    )
    # SHA-256 de l'image courante (NULL sans image). Dénormalisé : la synchro
    # transporte la version sans charger le binaire (voir ProductImage).
    image_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name!r} price={self.selling_price}>"


class ProductImage(Base):
    """Image d'un produit, ré-encodée en WebP par l'API (ADR-0008).

    Jamais chargée avec le produit : servie seulement par GET /products/{id}/image.
    """

    __tablename__ = "product_images"

    product_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE", name="fk_product_images_product"),
        primary_key=True,
    )
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_product_images_store"),
        nullable=False,
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
