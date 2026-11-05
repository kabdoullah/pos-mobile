"""admin audit log + lecture admin des produits.

Revision ID: a7c3e9f2b4d1
Revises: f3a9b1c7d2e5
Create Date: 2026-11-05

- admin_audit_log : journal des actions admin (connexion, suspension,
  réactivation). Table plateforme (pas de store_id tenant, pas de RLS), lue
  uniquement par les routes admin. Immuable (trigger UPDATE/DELETE). store_id
  sans clé étrangère : l'entrée survit à la purge de la boutique (ADR-0011).
  Seule mise à jour admise : admin_id passé à NULL par ON DELETE SET NULL.
  admin_id en ON DELETE SET NULL : supprimer la ligne admin (rotation du mot
  de passe, ADR-0012) reste possible, admin_email garde la trace.
- politique RLS additionnelle rls_products_platform_admin_read (lecture seule,
  conditionnée par app.is_platform_admin = 'on') pour compter les produits
  d'une boutique dans la fiche admin.

Schéma uniquement, aucune donnée modifiée.
Downgrade : supprime la politique, le trigger, la fonction et la table (le
journal est perdu).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f2b4d1"
down_revision: str | None = "f3a9b1c7d2e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN = "current_setting('app.is_platform_admin', true) = 'on'"


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "admin_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("platform_admins.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("admin_email", sa.String(255), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("store_name", sa.String(255), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            # clock_timestamp() : deux actions d'une même transaction restent ordonnées.
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.CheckConstraint(
            "action IN ('login', 'store_suspended', 'store_reactivated')",
            name="chk_admin_audit_log_action",
        ),
    )
    op.create_index(
        "ix_admin_audit_log_created_at", "admin_audit_log", [sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_admin_audit_log_store_created",
        "admin_audit_log",
        ["store_id", sa.text("created_at DESC")],
    )
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_admin_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Seule exception : ON DELETE SET NULL de admin_id (suppression de l'admin).
            IF TG_OP = 'UPDATE' AND NEW.admin_id IS NULL
               AND (NEW.id, NEW.admin_email, NEW.action, NEW.store_id, NEW.store_name,
                    NEW.reason, NEW.created_at)
                   IS NOT DISTINCT FROM
                   (OLD.id, OLD.admin_email, OLD.action, OLD.store_id, OLD.store_name,
                    OLD.reason, OLD.created_at) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'admin_audit_log table is immutable: % not allowed', TG_OP
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """)
    op.execute("""
        CREATE TRIGGER trg_admin_audit_log_immutable
            BEFORE UPDATE OR DELETE ON admin_audit_log
            FOR EACH ROW
            EXECUTE FUNCTION prevent_admin_audit_log_modification();
    """)
    op.execute(f"""
        CREATE POLICY rls_products_platform_admin_read ON products
            FOR SELECT USING ({_ADMIN});
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_products_platform_admin_read ON products;")
    op.execute("DROP TRIGGER IF EXISTS trg_admin_audit_log_immutable ON admin_audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_admin_audit_log_modification();")
    op.drop_index("ix_admin_audit_log_store_created", table_name="admin_audit_log")
    op.drop_index("ix_admin_audit_log_created_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
