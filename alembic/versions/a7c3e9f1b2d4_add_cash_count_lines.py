"""add cash count lines.

Revision ID: a7c3e9f1b2d4
Revises: b8f2d5a1c9e7
Create Date: 2026-11-14

Billetterie de caisse (ADR-0016) :
- cash_count_lines : table tenant (RLS), une ligne par coupure et par
  opération (opening / closing) d'une session de caisse. IMMUABLE (fonction
  prevent_sale_returns_modification, qui laisse passer la purge de compte) ;
- trigger prevent_count_line_on_closed_session : refuse toute ligne ajoutée à
  une session déjà clôturée (un comptage validé ne se complète pas après coup).
  Les lignes de clôture sont insérées AVANT l'UPDATE de clôture, dans la même
  transaction ;
- subtotal = denomination * quantity imposé par CHECK ; le total du comptage
  reste celui de la session (opening_amount / counted_amount).

purge_store (ADR-0011) est recréée pour supprimer aussi cash_count_lines avant
cash_sessions (FK RESTRICT).

Aucune donnée existante n'est modifiée : les sessions déjà enregistrées n'ont
simplement pas de comptage détaillé.

Downgrade : refusé s'il existe des lignes de comptage — ce sont des pièces
d'audit de caisse qu'on ne supprime pas.

ATTENTION : contient du SQL raw (RLS, triggers, fonctions) non détecté par
autogenerate, à l'image de 0001_initial_schema.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b2d4"
down_revision: str | None = "b8f2d5a1c9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_USING = "store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid"

# Ordre imposé par les clés étrangères (enfants avant parents). Version
# d'origine : b8f2d5a1c9e7_add_cash_register.
_PURGE_TABLES_BEFORE = (
    "stock_movements",
    "sale_return_items",
    "sale_returns",
    "sale_items",
    "sales",
    "cash_movements",
    "cash_sessions",
    "product_images",
    "products",
    "categories",
    "store_logos",
)
_PURGE_TABLES_AFTER = (
    "stock_movements",
    "sale_return_items",
    "sale_returns",
    "sale_items",
    "sales",
    "cash_movements",
    "cash_count_lines",
    "cash_sessions",
    "product_images",
    "products",
    "categories",
    "store_logos",
)


def _create_purge_store(tables: tuple[str, ...]) -> None:
    deletes = "\n".join(
        f"            DELETE FROM {table} WHERE store_id = p_store_id;" for table in tables
    )
    op.execute(f"""
        CREATE OR REPLACE FUNCTION purge_store(p_store_id uuid)
        RETURNS void
        SECURITY INVOKER
        AS $$
        DECLARE
            deleted_stores integer;
        BEGIN
            PERFORM set_config('app.purging_store_id', p_store_id::text, true);
{deletes}
            DELETE FROM stores WHERE id = p_store_id;
            GET DIAGNOSTICS deleted_stores = ROW_COUNT;
            PERFORM set_config('app.purging_store_id', '', true);
            IF deleted_stores = 0 THEN
                RAISE EXCEPTION 'purge_store: store % not deleted (not found or not visible)',
                    p_store_id;
            END IF;
        END;
        $$ language 'plpgsql';
    """)


def upgrade() -> None:
    # ============================================================
    # Fonction trigger : pas de comptage ajouté à une session clôturée
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_count_line_on_closed_session()
        RETURNS TRIGGER AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM cash_sessions
                WHERE id = NEW.session_id AND status = 'closed'
            ) THEN
                RAISE EXCEPTION 'cash_count_lines: session % is closed', NEW.session_id
                    USING ERRCODE = 'feature_not_supported';
            END IF;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table cash_count_lines
    # ============================================================
    op.create_table(
        "cash_count_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(10), nullable=False),
        sa.Column("denomination_type", sa.String(10), nullable=False),
        sa.Column("denomination", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_cash_count_lines_store", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["store_id", "session_id"],
            ["cash_sessions.store_id", "cash_sessions.id"],
            name="fk_cash_count_lines_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "session_id",
            "operation",
            "denomination_type",
            "denomination",
            name="uq_cash_count_lines_denomination",
        ),
        sa.CheckConstraint(
            "operation IN ('opening', 'closing')", name="chk_cash_count_lines_operation"
        ),
        sa.CheckConstraint(
            "denomination_type IN ('bill', 'coin')",
            name="chk_cash_count_lines_denomination_type",
        ),
        sa.CheckConstraint("denomination > 0", name="chk_cash_count_lines_denomination_positive"),
        sa.CheckConstraint("quantity >= 0", name="chk_cash_count_lines_quantity_positive"),
        sa.CheckConstraint(
            "subtotal = denomination * quantity", name="chk_cash_count_lines_subtotal"
        ),
    )
    op.create_index("idx_cash_count_lines_store_id", "cash_count_lines", ["store_id"])
    # L'index unique (session_id, operation, …) sert aussi les lectures par session.
    op.execute(
        "COMMENT ON TABLE cash_count_lines IS "
        "'Billetterie de caisse (ADR-0016). Table immuable. Aucun UPDATE/DELETE autorisé.';"
    )
    for operation in ("update", "delete"):
        op.execute(f"""
            CREATE TRIGGER trg_cash_count_lines_immutable_{operation}
                BEFORE {operation.upper()} ON cash_count_lines
                FOR EACH ROW
                EXECUTE FUNCTION prevent_sale_returns_modification();
        """)
    op.execute("""
        CREATE TRIGGER trg_cash_count_lines_session_open
            BEFORE INSERT ON cash_count_lines
            FOR EACH ROW
            EXECUTE FUNCTION prevent_count_line_on_closed_session();
    """)

    op.execute("ALTER TABLE cash_count_lines ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE cash_count_lines FORCE ROW LEVEL SECURITY;")
    op.execute(f"""
        CREATE POLICY rls_cash_count_lines_tenant_isolation ON cash_count_lines
            USING ({_RLS_USING})
            WITH CHECK ({_RLS_USING});
    """)

    _create_purge_store(_PURGE_TABLES_AFTER)


def downgrade() -> None:
    # Sans RLS pour le contrôle : sous FORCE RLS, le EXISTS verrait 0 ligne et
    # le downgrade détruirait les comptages (voir b8f2d5a1c9e7).
    op.execute("SET LOCAL row_security = off;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM cash_count_lines) THEN
                RAISE EXCEPTION 'Downgrade refusé : des comptages de caisse existent (ADR-0016).';
            END IF;
        END $$;
    """)

    _create_purge_store(_PURGE_TABLES_BEFORE)

    op.execute("DROP POLICY IF EXISTS rls_cash_count_lines_tenant_isolation ON cash_count_lines;")
    op.execute("ALTER TABLE cash_count_lines DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS trg_cash_count_lines_session_open ON cash_count_lines;")
    for operation in ("update", "delete"):
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_cash_count_lines_immutable_{operation} "
            "ON cash_count_lines;"
        )
    op.drop_index("idx_cash_count_lines_store_id", table_name="cash_count_lines")
    op.drop_table("cash_count_lines")
    op.execute("DROP FUNCTION IF EXISTS prevent_count_line_on_closed_session();")
