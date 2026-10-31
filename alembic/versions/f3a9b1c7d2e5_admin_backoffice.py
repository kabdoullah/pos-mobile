"""admin backoffice: suspension des boutiques, platform_admins, politiques RLS admin.

Revision ID: f3a9b1c7d2e5
Revises: e5b2c8d4f1a6
Create Date: 2026-10-31

- stores : colonnes suspended_at / suspension_reason ;
- platform_admins : table non tenant (pas de RLS) + trigger updated_at ;
- politiques RLS ADDITIONNELLES (permissives, donc combinées en OR avec les
  politiques tenant) conditionnées par app.is_platform_admin = 'on' :
  lecture de stores et sales, UPDATE de stores.

Schéma uniquement, aucune donnée modifiée.
Downgrade : supprime les politiques, la table et les colonnes ; supprimer
suspended_at réactive de fait toutes les boutiques suspendues.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3a9b1c7d2e5"
down_revision: str | None = "e5b2c8d4f1a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADMIN = "current_setting('app.is_platform_admin', true) = 'on'"


def upgrade() -> None:
    op.add_column("stores", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stores", sa.Column("suspension_reason", sa.String(500), nullable=True))

    op.create_table(
        "platform_admins",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_platform_admins_email"),
        sa.CheckConstraint("email = lower(email)", name="chk_platform_admins_email_lowercase"),
    )
    op.execute("""
        CREATE TRIGGER trg_platform_admins_updated_at
            BEFORE UPDATE ON platform_admins
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute(f"""
        CREATE POLICY rls_stores_platform_admin_read ON stores
            FOR SELECT USING ({_ADMIN});
    """)
    op.execute(f"""
        CREATE POLICY rls_stores_platform_admin_update ON stores
            FOR UPDATE USING ({_ADMIN}) WITH CHECK ({_ADMIN});
    """)
    op.execute(f"""
        CREATE POLICY rls_sales_platform_admin_read ON sales
            FOR SELECT USING ({_ADMIN});
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_sales_platform_admin_read ON sales;")
    op.execute("DROP POLICY IF EXISTS rls_stores_platform_admin_update ON stores;")
    op.execute("DROP POLICY IF EXISTS rls_stores_platform_admin_read ON stores;")
    op.execute("DROP TRIGGER IF EXISTS trg_platform_admins_updated_at ON platform_admins;")
    op.drop_table("platform_admins")
    op.drop_column("stores", "suspension_reason")
    op.drop_column("stores", "suspended_at")
