"""add customer returns.

Revision ID: d1a4f7c2e9b0
Revises: 6935928f6907
Create Date: 2026-10-17

Retours clients (ADR-0010) :
- sale_returns / sale_return_items : tables tenant IMMUABLES (trigger), RLS,
  id UUID généré côté client (idempotence du sync). Chaque ligne de retour
  référence la ligne de vente d'origine (sale_item_id) ;
- return_number séquentiel par boutique, posé par le trigger
  generate_return_number à partir de stores.next_return_number (même principe
  que receipt_number) ;
- stock_movements : nouveau motif customer_return et colonne sale_return_id
  (renseignée si et seulement si reason = customer_return).

Aucune donnée existante n'est modifiée. ALTER TYPE … ADD VALUE est exécuté hors
transaction (autocommit_block) : la nouvelle valeur ne peut pas être utilisée
dans la transaction qui l'a créée, or la contrainte CHECK ci-dessous la cite.

Downgrade : refusé s'il existe des retours — ce sont des écritures comptables
(argent rendu au client) qu'on ne supprime pas. Sans retour, le motif
customer_return est retiré en recréant le type ENUM.

ATTENTION : contient du SQL raw (RLS, triggers, ENUM) non détecté par
autogenerate, à l'image de 0001_initial_schema.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "d1a4f7c2e9b0"
down_revision: str | None = "6935928f6907"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_USING = "store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(f"""
        CREATE POLICY rls_{table}_tenant_isolation ON {table}
            USING ({_RLS_USING})
            WITH CHECK ({_RLS_USING});
    """)


def _immutable(table: str) -> None:
    for operation in ("update", "delete"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_immutable_{operation}
                BEFORE {operation.upper()} ON {table}
                FOR EACH ROW
                EXECUTE FUNCTION prevent_sale_returns_modification();
        """)


def upgrade() -> None:
    # ============================================================
    # Motif de mouvement de stock (hors transaction, voir docstring)
    # ============================================================
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE stock_movement_reason_enum ADD VALUE IF NOT EXISTS 'customer_return';"
        )

    # ============================================================
    # Compteur des numéros de retour
    # ============================================================
    op.add_column(
        "stores",
        sa.Column("next_return_number", sa.Integer, nullable=False, server_default=sa.text("1")),
    )
    op.create_check_constraint("chk_stores_next_return_number", "stores", "next_return_number >= 1")

    # ============================================================
    # Fonctions trigger
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION generate_return_number()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.return_number IS NOT NULL AND NEW.return_number > 0 THEN
                RETURN NEW;
            END IF;

            UPDATE stores
            SET next_return_number = next_return_number + 1
            WHERE id = NEW.store_id
            RETURNING next_return_number - 1 INTO NEW.return_number;

            IF NEW.return_number IS NULL THEN
                RAISE EXCEPTION 'Could not generate return_number for store_id %', NEW.store_id;
            END IF;

            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_sale_returns_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION '% table is immutable: % not allowed', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table sale_returns (immuable)
    # ============================================================
    op.create_table(
        "sale_returns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sale_id", UUID(as_uuid=True), nullable=False),
        sa.Column("return_number", sa.Integer, nullable=True),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("refund_method", sa.String(30), nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_sale_returns_store", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"], name="fk_sale_returns_sale", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_sale_returns_created_by", ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "store_id", "return_number", name="uq_sale_returns_store_return_number"
        ),
        sa.CheckConstraint(
            "reason IN ('defective', 'damaged', 'wrong_product', 'sale_error', "
            "'changed_mind', 'other')",
            name="chk_sale_returns_reason",
        ),
        sa.CheckConstraint(
            "reason != 'other' OR (note IS NOT NULL AND length(trim(note)) > 0)",
            name="chk_sale_returns_other_requires_note",
        ),
        sa.CheckConstraint(
            "refund_method IN ('cash', 'mobile_money_orange', 'mobile_money_mtn', "
            "'mobile_money_wave')",
            name="chk_sale_returns_refund_method",
        ),
        sa.CheckConstraint("refund_amount >= 0", name="chk_sale_returns_refund_amount_positive"),
    )
    op.create_index("idx_sale_returns_sale_id", "sale_returns", ["sale_id"])
    op.create_index("idx_sale_returns_store_synced_at", "sale_returns", ["store_id", "synced_at"])
    op.execute("COMMENT ON TABLE sale_returns IS 'Table immuable. Aucun UPDATE/DELETE autorisé.';")
    op.execute(
        "COMMENT ON COLUMN sale_returns.id IS 'UUID v4 généré côté client pour idempotence sync';"
    )
    op.execute(
        "COMMENT ON COLUMN sale_returns.return_number IS 'Généré par trigger generate_return_number';"
    )
    op.execute(
        "COMMENT ON COLUMN sale_returns.refund_amount IS "
        "'Montant rendu au client, confirmé au comptoir (remboursement manuel)';"
    )

    op.execute("""
        CREATE TRIGGER trg_sale_returns_return_number
            BEFORE INSERT ON sale_returns
            FOR EACH ROW
            EXECUTE FUNCTION generate_return_number();
    """)
    _immutable("sale_returns")
    _enable_rls("sale_returns")

    # ============================================================
    # Table sale_return_items (immuable)
    # ============================================================
    op.create_table(
        "sale_return_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sale_return_id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sale_item_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("restocked", sa.Boolean, nullable=False),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_return_id"],
            ["sale_returns.id"],
            name="fk_sale_return_items_return",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_sale_return_items_store", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sale_item_id"],
            ["sale_items.id"],
            name="fk_sale_return_items_sale_item",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name="fk_sale_return_items_product",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("quantity > 0", name="chk_sale_return_items_quantity_positive"),
        sa.CheckConstraint(
            "condition IN ('resellable', 'damaged', 'defective', 'unsellable')",
            name="chk_sale_return_items_condition",
        ),
        sa.CheckConstraint(
            "NOT restocked OR condition = 'resellable'",
            name="chk_sale_return_items_restocked_resellable",
        ),
        sa.CheckConstraint(
            "refund_amount >= 0", name="chk_sale_return_items_refund_amount_positive"
        ),
    )
    op.create_index("idx_sale_return_items_return_id", "sale_return_items", ["sale_return_id"])
    op.create_index("idx_sale_return_items_sale_item_id", "sale_return_items", ["sale_item_id"])
    op.create_index("idx_sale_return_items_store_id", "sale_return_items", ["store_id"])
    op.execute(
        "COMMENT ON TABLE sale_return_items IS 'Table immuable. Aucun UPDATE/DELETE autorisé.';"
    )
    op.execute("COMMENT ON COLUMN sale_return_items.store_id IS 'Dénormalisé pour le RLS';")
    _immutable("sale_return_items")
    _enable_rls("sale_return_items")

    # ============================================================
    # stock_movements : lien vers le retour
    # ============================================================
    op.add_column("stock_movements", sa.Column("sale_return_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_stock_movements_sale_return",
        "stock_movements",
        "sale_returns",
        ["sale_return_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "chk_stock_movements_sale_return_id_matches_reason",
        "stock_movements",
        "(reason = 'customer_return') = (sale_return_id IS NOT NULL)",
    )
    op.execute("""
        CREATE INDEX idx_stock_movements_sale_return_id ON stock_movements (sale_return_id)
            WHERE sale_return_id IS NOT NULL;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM sale_returns) THEN
                RAISE EXCEPTION 'Downgrade refusé : des retours clients existent (ADR-0010).';
            END IF;
        END $$;
    """)

    op.execute("DROP INDEX IF EXISTS idx_stock_movements_sale_return_id;")
    op.drop_constraint(
        "chk_stock_movements_sale_return_id_matches_reason", "stock_movements", type_="check"
    )
    op.drop_constraint("fk_stock_movements_sale_return", "stock_movements", type_="foreignkey")
    op.drop_column("stock_movements", "sale_return_id")

    for table in ("sale_return_items", "sale_returns"):
        op.execute(f"DROP POLICY IF EXISTS rls_{table}_tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_delete ON {table};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_immutable_update ON {table};")
    op.execute("DROP TRIGGER IF EXISTS trg_sale_returns_return_number ON sale_returns;")
    op.drop_table("sale_return_items")
    op.drop_table("sale_returns")

    op.execute("DROP FUNCTION IF EXISTS prevent_sale_returns_modification();")
    op.execute("DROP FUNCTION IF EXISTS generate_return_number();")

    op.drop_constraint("chk_stores_next_return_number", "stores", type_="check")
    op.drop_column("stores", "next_return_number")

    # PostgreSQL ne sait pas retirer une valeur d'ENUM : recréation du type.
    # Aucun mouvement customer_return ne peut subsister (la contrainte retirée
    # ci-dessus imposait un sale_return_id, et aucun retour n'existe). La
    # contrainte qui compare reason à un littéral est retirée pendant le
    # changement de type puis recréée à l'identique.
    op.drop_constraint(
        "chk_stock_movements_sale_id_matches_reason", "stock_movements", type_="check"
    )
    op.execute("ALTER TYPE stock_movement_reason_enum RENAME TO stock_movement_reason_enum_old;")
    op.execute(
        "CREATE TYPE stock_movement_reason_enum AS ENUM "
        "('sale', 'manual_adjustment', 'catalog_update');"
    )
    op.execute("""
        ALTER TABLE stock_movements
            ALTER COLUMN reason TYPE stock_movement_reason_enum
            USING reason::text::stock_movement_reason_enum;
    """)
    op.execute("DROP TYPE stock_movement_reason_enum_old;")
    op.create_check_constraint(
        "chk_stock_movements_sale_id_matches_reason",
        "stock_movements",
        "(reason = 'sale') = (sale_id IS NOT NULL)",
    )
