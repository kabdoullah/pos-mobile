"""add categories.

Revision ID: a8d3c1f0e2b4
Revises: c23a8cbb0937
Create Date: 2026-09-27

Ajoute la table categories (catégories de produits, synchronisées par état
comme le catalogue) et la colonne products.category_id.

- Une catégorie appartient à une boutique (store_id + RLS).
- Nom unique par boutique, insensible à la casse, parmi les catégories non
  supprimées (index unique partiel) : une catégorie supprimée libère son nom.
- Soft delete via deleted_at. La suppression détache les produits
  (category_id -> NULL) côté service, dans la même transaction.
- Un produit a au plus une catégorie.

Aucune donnée existante n'est modifiée : products.category_id est nullable.

ATTENTION : contient du SQL raw (RLS, trigger, index partiel) non détecté par
autogenerate, à l'image de 0001_initial_schema.py.

Voir docs/adr/0008-categories-images-recus.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "a8d3c1f0e2b4"
down_revision: str | None = "c23a8cbb0937"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================================
    # Table categories
    # ============================================================
    op.create_table(
        "categories",
        # Pas de valeur par défaut serveur : l'id est généré par le client
        # (création hors ligne) ou par l'API (uuid4 côté modèle).
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_categories_store", ondelete="RESTRICT"
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="chk_categories_name_not_empty"),
    )

    op.execute("CREATE INDEX idx_categories_store ON categories (store_id);")
    op.execute("""
        CREATE UNIQUE INDEX uq_categories_store_name_active
            ON categories (store_id, lower(name))
            WHERE deleted_at IS NULL;
    """)

    op.execute("COMMENT ON COLUMN categories.deleted_at IS 'Soft delete : NULL = active';")

    op.execute("""
        CREATE TRIGGER trg_categories_updated_at
            BEFORE UPDATE ON categories
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # RLS sur categories (même politique que products)
    op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE categories FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_categories_tenant_isolation ON categories
            USING (store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid)
            WITH CHECK (store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid);
    """)

    # ============================================================
    # products.category_id
    # ============================================================
    op.add_column("products", sa.Column("category_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_products_category",
        "products",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("""
        CREATE INDEX idx_products_category ON products (category_id)
            WHERE category_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_products_category;")
    op.drop_constraint("fk_products_category", "products", type_="foreignkey")
    op.drop_column("products", "category_id")

    op.execute("DROP POLICY IF EXISTS rls_categories_tenant_isolation ON categories;")
    op.execute("ALTER TABLE categories DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS trg_categories_updated_at ON categories;")
    op.drop_table("categories")
