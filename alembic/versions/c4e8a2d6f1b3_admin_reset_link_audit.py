"""admin audit log : liens de reset générés par le support (ADR-0014).

Revision ID: c4e8a2d6f1b3
Revises: a7c3e9f2b4d1
Create Date: 2026-11-05

- admin_audit_log.user_id (UUID, sans clé étrangère : l'entrée survit à la
  suppression du compte, ADR-0011) et user_phone (copié).
- chk_admin_audit_log_action accepte 'user_password_reset_link'.
- Le trigger d'immuabilité couvre les nouvelles colonnes.

Schéma uniquement, aucune donnée modifiée à l'upgrade.
Downgrade : supprime les entrées 'user_password_reset_link' (trigger
d'immuabilité désactivé le temps du DELETE), puis les colonnes. Ces entrées
du journal sont perdues.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4e8a2d6f1b3"
down_revision: str | None = "a7c3e9f2b4d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = "action IN ('login', 'store_suspended', 'store_reactivated')"
_NEW_ACTIONS = (
    "action IN ('login', 'store_suspended', 'store_reactivated', 'user_password_reset_link')"
)
_OLD_COLUMNS = "id, admin_email, action, store_id, store_name, reason, created_at"
_NEW_COLUMNS = (
    "id, admin_email, action, store_id, store_name, user_id, user_phone, reason, created_at"
)


def _immutability_function(columns: str) -> str:
    new = ", ".join(f"NEW.{c}" for c in columns.split(", "))
    old = ", ".join(f"OLD.{c}" for c in columns.split(", "))
    return f"""
        CREATE OR REPLACE FUNCTION prevent_admin_audit_log_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Seule exception : ON DELETE SET NULL de admin_id (suppression de l'admin).
            IF TG_OP = 'UPDATE' AND NEW.admin_id IS NULL
               AND ({new}) IS NOT DISTINCT FROM ({old}) THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'admin_audit_log table is immutable: % not allowed', TG_OP
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """


def upgrade() -> None:
    op.add_column("admin_audit_log", sa.Column("user_id", postgresql.UUID(as_uuid=True)))
    op.add_column("admin_audit_log", sa.Column("user_phone", sa.String(20)))
    op.drop_constraint("chk_admin_audit_log_action", "admin_audit_log", type_="check")
    op.create_check_constraint("chk_admin_audit_log_action", "admin_audit_log", _NEW_ACTIONS)
    op.execute(_immutability_function(_NEW_COLUMNS))


def downgrade() -> None:
    op.execute(_immutability_function(_OLD_COLUMNS))
    op.execute("ALTER TABLE admin_audit_log DISABLE TRIGGER trg_admin_audit_log_immutable;")
    op.execute("DELETE FROM admin_audit_log WHERE action = 'user_password_reset_link';")
    op.execute("ALTER TABLE admin_audit_log ENABLE TRIGGER trg_admin_audit_log_immutable;")
    op.drop_constraint("chk_admin_audit_log_action", "admin_audit_log", type_="check")
    op.create_check_constraint("chk_admin_audit_log_action", "admin_audit_log", _OLD_ACTIONS)
    op.drop_column("admin_audit_log", "user_phone")
    op.drop_column("admin_audit_log", "user_id")
