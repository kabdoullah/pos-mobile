"""add min_stock to products.

Revision ID: c23a8cbb0937
Revises: ebc43628c0d3
Create Date: 2026-08-14

Ajoute products.min_stock (seuil de réapprovisionnement, INTEGER NULL) : champ
déclaratif au même titre que name/unit_price, pas tracé dans stock_movements
(ce n'est pas une quantité de stock, juste une config de seuil).

Note : l'autogenerate d'Alembic a aussi détecté un écart massif (index/commentaires
créés en SQL brut dans 0001_initial_schema.py et ebc43628c0d3, non reflétés dans
les métadonnées SQLAlchemy) ; ce bruit a été retiré manuellement de cette migration,
qui ne contient que le changement réellement voulu.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c23a8cbb0937"
down_revision: str | None = "ebc43628c0d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("min_stock", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "chk_products_min_stock_non_negative",
        "products",
        "min_stock IS NULL OR min_stock >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("chk_products_min_stock_non_negative", "products", type_="check")
    op.drop_column("products", "min_stock")
