"""add pricing, discounts and margin snapshot.

Revision ID: 6935928f6907
Revises: c7f1e5b9d3a2
Create Date: 2026-09-27

Prix d'achat, réductions et marge (ADR-0009) :
- products.unit_price est RENOMMÉE en selling_price (pas de perte : RENAME
  COLUMN, contrainte CHECK renommée) ; products.purchase_price est ajoutée,
  NULL = non renseigné pour tous les produits existants (on n'invente pas de
  coût : 0 fausserait la marge, le prix de vente aussi) ;
- sale_items : instantané du prix d'achat (purchase_price_at_sale, NULL pour
  les ventes passées) et de la réduction de ligne (discount_type,
  discount_value, discount_amount = 0 par défaut) ;
- sales : remise globale (discount_type, discount_value, discount_amount).

La contrainte chk_sale_items_line_total devient
line_total = unit_price_at_sale * quantity - discount_amount : les lignes
existantes (discount_amount = 0) la satisfont. Aucune donnée existante n'est
modifiée. ADD COLUMN est du DDL : il ne déclenche pas les triggers
d'immuabilité de sales (UPDATE/DELETE de lignes).

Downgrade : refusé s'il existe des ventes avec réduction — l'ancienne
contrainte line_total = unit_price_at_sale * quantity serait violée et le
montant réellement payé ne pourrait plus être reconstruit. Les prix d'achat
saisis sont perdus au downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6935928f6907"
down_revision: str | None = "c7f1e5b9d3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DISCOUNT_TYPE_CHECK = "discount_type IS NULL OR discount_type IN ('amount', 'percentage')"


def _discount_columns(table: str) -> None:
    op.add_column(table, sa.Column("discount_type", sa.String(10), nullable=True))
    op.add_column(table, sa.Column("discount_value", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        table,
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(f"chk_{table}_discount_type", table, _DISCOUNT_TYPE_CHECK)


def upgrade() -> None:
    # --- products ---
    op.alter_column("products", "unit_price", new_column_name="selling_price")
    op.execute(
        "ALTER TABLE products RENAME CONSTRAINT chk_products_unit_price_positive "
        "TO chk_products_selling_price_positive;"
    )
    op.add_column("products", sa.Column("purchase_price", sa.Numeric(12, 2), nullable=True))
    op.create_check_constraint(
        "chk_products_purchase_price_positive",
        "products",
        "purchase_price IS NULL OR purchase_price >= 0",
    )

    # --- sales : remise globale ---
    _discount_columns("sales")
    op.create_check_constraint(
        "chk_sales_discount_amount_positive", "sales", "discount_amount >= 0"
    )

    # --- sale_items : instantané prix d'achat + réduction de ligne ---
    op.add_column(
        "sale_items", sa.Column("purchase_price_at_sale", sa.Numeric(12, 2), nullable=True)
    )
    op.create_check_constraint(
        "chk_sale_items_purchase_price_positive",
        "sale_items",
        "purchase_price_at_sale IS NULL OR purchase_price_at_sale >= 0",
    )
    _discount_columns("sale_items")
    op.drop_constraint("chk_sale_items_line_total", "sale_items", type_="check")
    op.create_check_constraint(
        "chk_sale_items_line_total",
        "sale_items",
        "line_total = unit_price_at_sale * quantity - discount_amount",
    )
    op.create_check_constraint(
        "chk_sale_items_discount_amount",
        "sale_items",
        "discount_amount >= 0 AND discount_amount <= unit_price_at_sale * quantity",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM sale_items WHERE discount_amount <> 0)
               OR EXISTS (SELECT 1 FROM sales WHERE discount_amount <> 0) THEN
                RAISE EXCEPTION 'downgrade refusé : des ventes portent une réduction (ADR-0009)';
            END IF;
        END $$;
        """
    )

    op.drop_constraint("chk_sale_items_discount_amount", "sale_items", type_="check")
    op.drop_constraint("chk_sale_items_line_total", "sale_items", type_="check")
    op.create_check_constraint(
        "chk_sale_items_line_total", "sale_items", "line_total = unit_price_at_sale * quantity"
    )
    op.drop_constraint("chk_sales_discount_amount_positive", "sales", type_="check")
    for table in ("sale_items", "sales"):
        op.drop_constraint(f"chk_{table}_discount_type", table, type_="check")
        op.drop_column(table, "discount_amount")
        op.drop_column(table, "discount_value")
        op.drop_column(table, "discount_type")
    op.drop_constraint("chk_sale_items_purchase_price_positive", "sale_items", type_="check")
    op.drop_column("sale_items", "purchase_price_at_sale")

    op.drop_constraint("chk_products_purchase_price_positive", "products", type_="check")
    op.drop_column("products", "purchase_price")
    op.execute(
        "ALTER TABLE products RENAME CONSTRAINT chk_products_selling_price_positive "
        "TO chk_products_unit_price_positive;"
    )
    op.alter_column("products", "selling_price", new_column_name="unit_price")
