"""add stock_movements table.

Revision ID: ebc43628c0d3
Revises: ceee847173d3
Create Date: 2026-08-02

Ajoute la table stock_movements : ledger append-only et immuable qui trace
toute variation de current_stock (vente, ajustement manuel, PATCH produit,
sync catalogue) — qui/quand/pourquoi.

Relâche aussi chk_products_current_stock_non_negative sur products : une vente
ne bloque jamais sur stock insuffisant, current_stock peut devenir négatif
(décision produit actée, voir docs/adr/0007-stock-movements.md).

ATTENTION : contient du SQL raw (RLS, triggers) non détecté par autogenerate,
à l'image de 0001_initial_schema.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

# revision identifiers, used by Alembic.
revision: str = "ebc43628c0d3"
down_revision: str | None = "ceee847173d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================================
    # Stock ne bloque jamais une vente : current_stock peut être négatif
    # ============================================================
    op.drop_constraint("chk_products_current_stock_non_negative", "products", type_="check")

    # ============================================================
    # Type ENUM
    # ============================================================
    stock_movement_reason_enum = ENUM(
        "sale",
        "manual_adjustment",
        "catalog_update",
        name="stock_movement_reason_enum",
        create_type=True,
    )
    stock_movement_reason_enum.create(op.get_bind(), checkfirst=False)

    # ============================================================
    # Fonction d'immuabilité de stock_movements (mirroring prevent_sales_modification)
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_stock_movements_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'stock_movements table is immutable: % not allowed', TG_OP
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table stock_movements (immuable)
    # ============================================================
    op.create_table(
        "stock_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_delta", sa.Integer, nullable=True),
        sa.Column(
            "reason",
            ENUM(
                "sale", "manual_adjustment", "catalog_update",
                name="stock_movement_reason_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("resulting_stock", sa.Integer, nullable=True),
        sa.Column("sale_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"],
            name="fk_stock_movements_store", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_stock_movements_product", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"],
            name="fk_stock_movements_sale", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_stock_movements_created_by", ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "quantity_delta IS NOT NULL OR resulting_stock IS NULL",
            name="chk_stock_movements_null_delta_implies_null_resulting_stock",
        ),
        sa.CheckConstraint(
            "(reason = 'sale') = (sale_id IS NOT NULL)",
            name="chk_stock_movements_sale_id_matches_reason",
        ),
    )

    op.execute("""
        CREATE INDEX idx_stock_movements_store_created_at
            ON stock_movements (store_id, created_at DESC);
    """)
    op.execute("""
        CREATE INDEX idx_stock_movements_store_product_created_at
            ON stock_movements (store_id, product_id, created_at DESC);
    """)
    op.execute("""
        CREATE INDEX idx_stock_movements_sale_id ON stock_movements (sale_id)
            WHERE sale_id IS NOT NULL;
    """)

    op.execute(
        "COMMENT ON COLUMN stock_movements.quantity_delta IS "
        "'NULL = désactivation du tracking (current_stock -> NULL), pas un delta numérique';"
    )
    op.execute(
        "COMMENT ON COLUMN stock_movements.resulting_stock IS "
        "'Snapshot de current_stock après ce mouvement. Peut être négatif : "
        "une vente ne bloque jamais sur stock insuffisant.';"
    )
    op.execute("COMMENT ON COLUMN stock_movements.sale_id IS 'Renseigné seulement si reason=sale';")
    op.execute("COMMENT ON COLUMN stock_movements.created_by IS 'Utilisateur à l''origine du mouvement';")
    op.execute("COMMENT ON TABLE stock_movements IS 'Table immuable (append-only). Aucun UPDATE/DELETE autorisé.';")

    # Triggers d'immuabilité
    op.execute("""
        CREATE TRIGGER trg_stock_movements_immutable_update
            BEFORE UPDATE ON stock_movements
            FOR EACH ROW
            EXECUTE FUNCTION prevent_stock_movements_modification();
    """)
    op.execute("""
        CREATE TRIGGER trg_stock_movements_immutable_delete
            BEFORE DELETE ON stock_movements
            FOR EACH ROW
            EXECUTE FUNCTION prevent_stock_movements_modification();
    """)

    # RLS sur stock_movements
    op.execute("ALTER TABLE stock_movements ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE stock_movements FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_stock_movements_tenant_isolation ON stock_movements
            USING (store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid)
            WITH CHECK (store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_stock_movements_tenant_isolation ON stock_movements;")
    op.execute("ALTER TABLE stock_movements DISABLE ROW LEVEL SECURITY;")

    op.execute("DROP TRIGGER IF EXISTS trg_stock_movements_immutable_delete ON stock_movements;")
    op.execute("DROP TRIGGER IF EXISTS trg_stock_movements_immutable_update ON stock_movements;")

    op.drop_table("stock_movements")

    op.execute("DROP FUNCTION IF EXISTS prevent_stock_movements_modification();")
    op.execute("DROP TYPE IF EXISTS stock_movement_reason_enum;")

    op.create_check_constraint(
        "chk_products_current_stock_non_negative",
        "products",
        "current_stock IS NULL OR current_stock >= 0",
    )
