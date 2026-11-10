"""add cash register.

Revision ID: b8f2d5a1c9e7
Revises: c4e8a2d6f1b3
Create Date: 2026-11-10

Sessions de caisse par appareil (ADR-0015) :
- cash_sessions : table tenant (RLS), id UUID généré côté client. Une seule
  session ouverte par appareil (index unique partiel). Une session clôturée
  est figée : le trigger prevent_closed_cash_session_modification refuse tout
  UPDATE d'une ligne closed et tout DELETE ;
- cash_movements : entrées/sorties d'espèces hors ventes, table tenant
  IMMUABLE (fonction prevent_sale_returns_modification, déjà générique) ;
- sales.cash_session_id et sale_returns.cash_session_id : rattachement
  optionnel à une session, posé à l'INSERT. Les lignes existantes restent NULL.

purge_store (ADR-0011) est recréée pour supprimer aussi cash_movements et
cash_sessions : sans cela, la FK RESTRICT stores ← cash_sessions bloquerait la
suppression de compte. Le trigger des sessions laisse passer un DELETE pendant
la purge de la boutique, comme les autres fonctions d'immuabilité.

Aucune donnée existante n'est modifiée (ADD COLUMN nullable).

Downgrade : refusé s'il existe des sessions de caisse — ce sont des écritures
comptables (fonds de caisse, écarts) qu'on ne supprime pas. Sans session,
aucun mouvement ni rattachement de vente/retour ne peut exister.

ATTENTION : contient du SQL raw (RLS, triggers, fonctions, index partiels) non
détecté par autogenerate, à l'image de 0001_initial_schema.py.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "b8f2d5a1c9e7"
down_revision: str | None = "c4e8a2d6f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_USING = "store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid"

# Champs renseignés à la clôture. closed_by (FK SET NULL), closing_note
# (exigée seulement en cas d'écart) et client_expected_amount (traçabilité)
# sont nuls tant que la session est ouverte, mais facultatifs une fois close.
_CLOSING_REQUIRED = (
    "expected_amount",
    "counted_amount",
    "discrepancy_amount",
    "closed_at",
    "closure_recorded_at",
)
_CLOSING_OPTIONAL = ("client_expected_amount", "closing_note", "closed_by")

# Ordre imposé par les clés étrangères (enfants avant parents). Version
# d'origine : e5b2c8d4f1a6_account_deletion_purge_store.
_PURGE_TABLES_BEFORE = (
    "stock_movements",
    "sale_return_items",
    "sale_returns",
    "sale_items",
    "sales",
    "product_images",
    "products",
    "categories",
    "store_logos",
)
# sales et sale_returns référencent cash_sessions : purgées avant elle.
_PURGE_TABLES_AFTER = (
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


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(f"""
        CREATE POLICY rls_{table}_tenant_isolation ON {table}
            USING ({_RLS_USING})
            WITH CHECK ({_RLS_USING});
    """)


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
    # Fonction trigger : session clôturée figée, jamais supprimée
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_closed_cash_session_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.store_id = NULLIF(current_setting('app.purging_store_id', true), '')::uuid
                THEN
                    RETURN OLD;
                END IF;
                RAISE EXCEPTION 'cash_sessions: DELETE not allowed'
                    USING ERRCODE = 'feature_not_supported';
            END IF;
            IF OLD.status = 'closed' THEN
                RAISE EXCEPTION 'cash_sessions: closed session cannot be modified'
                    USING ERRCODE = 'feature_not_supported';
            END IF;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table cash_sessions
    # ============================================================
    open_state = " AND ".join(f"{c} IS NULL" for c in _CLOSING_REQUIRED + _CLOSING_OPTIONAL)
    closed_state = " AND ".join(f"{c} IS NOT NULL" for c in _CLOSING_REQUIRED)
    op.create_table(
        "cash_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("opening_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("opening_note", sa.String(500), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_by", UUID(as_uuid=True), nullable=True),
        sa.Column("expected_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("client_expected_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("counted_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("discrepancy_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("closing_note", sa.String(500), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("closure_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_cash_sessions_store", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["opened_by"], ["users.id"], name="fk_cash_sessions_opened_by", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["closed_by"], ["users.id"], name="fk_cash_sessions_closed_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint("status IN ('open', 'closed')", name="chk_cash_sessions_status"),
        sa.CheckConstraint(
            "opening_amount >= 0", name="chk_cash_sessions_opening_amount_positive"
        ),
        sa.CheckConstraint(
            "counted_amount IS NULL OR counted_amount >= 0",
            name="chk_cash_sessions_counted_amount_positive",
        ),
        sa.CheckConstraint(
            f"(status = 'open' AND {open_state}) "
            f"OR (status = 'closed' AND {closed_state} "
            "AND discrepancy_amount = counted_amount - expected_amount)",
            name="chk_cash_sessions_state",
        ),
        sa.CheckConstraint(
            "status <> 'closed' OR discrepancy_amount = 0 "
            "OR (closing_note IS NOT NULL AND length(trim(closing_note)) > 0)",
            name="chk_cash_sessions_note_on_discrepancy",
        ),
        sa.CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at",
            name="chk_cash_sessions_closed_after_opened",
        ),
    )
    # Sert aussi d'index sur store_id (colonne de tête).
    op.execute("""
        CREATE INDEX idx_cash_sessions_store_opened_at
            ON cash_sessions (store_id, opened_at DESC);
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_cash_sessions_open_per_device
            ON cash_sessions (store_id, device_id) WHERE status = 'open';
    """)
    op.execute(
        "COMMENT ON TABLE cash_sessions IS "
        "'Session de caisse par appareil. Clôturée : figée. Aucun DELETE autorisé.';"
    )
    op.execute(
        "COMMENT ON COLUMN cash_sessions.id IS 'UUID v4 généré côté client pour idempotence sync';"
    )
    op.execute(
        "COMMENT ON COLUMN cash_sessions.expected_amount IS "
        "'Recalculé par le serveur à la clôture';"
    )
    op.execute(
        "COMMENT ON COLUMN cash_sessions.client_expected_amount IS "
        "'Montant attendu affiché par l''app (traçabilité, jamais utilisé pour le calcul)';"
    )

    op.execute("""
        CREATE TRIGGER set_updated_at
            BEFORE UPDATE ON cash_sessions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)
    op.execute("""
        CREATE TRIGGER trg_cash_sessions_prevent_closed_modification
            BEFORE UPDATE OR DELETE ON cash_sessions
            FOR EACH ROW
            EXECUTE FUNCTION prevent_closed_cash_session_modification();
    """)
    _enable_rls("cash_sessions")

    # ============================================================
    # Table cash_movements (immuable)
    # ============================================================
    op.create_table(
        "cash_movements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_cash_movements_store", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["cash_sessions.id"],
            name="fk_cash_movements_session",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_cash_movements_created_by", ondelete="SET NULL"
        ),
        sa.CheckConstraint("type IN ('cash_in', 'cash_out')", name="chk_cash_movements_type"),
        sa.CheckConstraint(
            "(type = 'cash_in' AND reason IN ('top_up', 'float', 'other')) "
            "OR (type = 'cash_out' AND reason IN ('expense', 'withdrawal', 'supplies', 'other'))",
            name="chk_cash_movements_reason",
        ),
        sa.CheckConstraint("amount > 0", name="chk_cash_movements_amount_positive"),
        sa.CheckConstraint(
            "reason <> 'other' OR (note IS NOT NULL AND length(trim(note)) > 0)",
            name="chk_cash_movements_other_requires_note",
        ),
    )
    op.create_index("idx_cash_movements_store_id", "cash_movements", ["store_id"])
    op.create_index("idx_cash_movements_session_id", "cash_movements", ["session_id"])
    op.execute(
        "COMMENT ON TABLE cash_movements IS 'Table immuable. Aucun UPDATE/DELETE autorisé.';"
    )
    op.execute(
        "COMMENT ON COLUMN cash_movements.id IS 'UUID v4 généré côté client pour idempotence sync';"
    )
    for operation in ("update", "delete"):
        op.execute(f"""
            CREATE TRIGGER trg_cash_movements_immutable_{operation}
                BEFORE {operation.upper()} ON cash_movements
                FOR EACH ROW
                EXECUTE FUNCTION prevent_sale_returns_modification();
        """)
    _enable_rls("cash_movements")

    # ============================================================
    # Rattachement des ventes et retours à une session
    # ============================================================
    for table in ("sales", "sale_returns"):
        op.add_column(table, sa.Column("cash_session_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_cash_session",
            table,
            "cash_sessions",
            ["cash_session_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.execute(f"""
            CREATE INDEX idx_{table}_cash_session_id ON {table} (cash_session_id)
                WHERE cash_session_id IS NOT NULL;
        """)

    _create_purge_store(_PURGE_TABLES_AFTER)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM cash_sessions) THEN
                RAISE EXCEPTION 'Downgrade refusé : des sessions de caisse existent (ADR-0015).';
            END IF;
        END $$;
    """)

    _create_purge_store(_PURGE_TABLES_BEFORE)

    for table in ("sale_returns", "sales"):
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_cash_session_id;")
        op.drop_constraint(f"fk_{table}_cash_session", table, type_="foreignkey")
        op.drop_column(table, "cash_session_id")

    op.execute("DROP POLICY IF EXISTS rls_cash_movements_tenant_isolation ON cash_movements;")
    op.execute("ALTER TABLE cash_movements DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP TRIGGER IF EXISTS trg_cash_movements_immutable_delete ON cash_movements;")
    op.execute("DROP TRIGGER IF EXISTS trg_cash_movements_immutable_update ON cash_movements;")
    op.drop_table("cash_movements")

    op.execute("DROP POLICY IF EXISTS rls_cash_sessions_tenant_isolation ON cash_sessions;")
    op.execute("ALTER TABLE cash_sessions DISABLE ROW LEVEL SECURITY;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_cash_sessions_prevent_closed_modification ON cash_sessions;"
    )
    op.execute("DROP TRIGGER IF EXISTS set_updated_at ON cash_sessions;")
    op.drop_table("cash_sessions")

    op.execute("DROP FUNCTION IF EXISTS prevent_closed_cash_session_modification();")
