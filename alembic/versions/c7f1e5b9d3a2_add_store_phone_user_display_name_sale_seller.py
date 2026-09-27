"""add store phone, user display name and sale seller.

Revision ID: c7f1e5b9d3a2
Revises: b4e9d2a7c1f3
Create Date: 2026-09-27

Reçus enrichis (ADR-0008) :
- stores.phone : téléphone de la boutique (E.164), imprimé sous l'adresse ;
- users.display_name : nom du vendeur, imprimé « Vendeur : … » ;
- sales.created_by : utilisateur à l'origine de la vente. Nécessaire pour
  que le reçu PDF, généré plus tard par le serveur, affiche le bon vendeur
  (et le reste le jour où plusieurs vendeurs partagent une boutique).

Colonnes nullables, aucune donnée existante modifiée : les ventes passées
n'ont pas de vendeur connu. L'ajout de colonne n'est pas bloqué par le
trigger d'immuabilité de sales (DDL, pas un UPDATE) ; created_by est posé
à l'INSERT.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "c7f1e5b9d3a2"
down_revision: str | None = "b4e9d2a7c1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("phone", sa.String(20), nullable=True))
    op.create_check_constraint(
        "chk_stores_phone_e164", "stores", "phone IS NULL OR phone ~ '^\\+[1-9][0-9]{6,14}$'"
    )

    op.add_column("users", sa.Column("display_name", sa.String(80), nullable=True))
    op.create_check_constraint(
        "chk_users_display_name_not_blank",
        "users",
        "display_name IS NULL OR length(trim(display_name)) > 0",
    )

    op.add_column("sales", sa.Column("created_by", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_sales_created_by", "sales", "users", ["created_by"], ["id"], ondelete="SET NULL"
    )
    op.execute(
        "COMMENT ON COLUMN sales.created_by IS "
        "'Vendeur (utilisateur du JWT à la synchro). NULL pour les ventes antérieures.';"
    )


def downgrade() -> None:
    op.drop_constraint("fk_sales_created_by", "sales", type_="foreignkey")
    op.drop_column("sales", "created_by")
    op.drop_constraint("chk_users_display_name_not_blank", "users", type_="check")
    op.drop_column("users", "display_name")
    op.drop_constraint("chk_stores_phone_e164", "stores", type_="check")
    op.drop_column("stores", "phone")
