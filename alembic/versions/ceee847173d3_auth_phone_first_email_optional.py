"""auth-phone-first-email-optional.

Revision ID: ceee847173d3
Revises: 0001_initial_schema
Create Date: 2026-06-07 18:42:12.091757

Rend email nullable sur users (optionnel, pour récupération seulement).
phone_number devient l'identifiant unique principal.

Downgrade : remet email NOT NULL. Requiert que toutes les lignes aient
un email non NULL avant d'appliquer le downgrade — sinon PostgreSQL rejette.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ceee847173d3"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Nettoyage des données existantes avant d'appliquer les contraintes ---

    # 1. Supprimer les espaces dans les numéros (ex: "+225 01 02 03 04 05")
    op.execute("UPDATE users SET phone_number = regexp_replace(phone_number, '\\s+', '', 'g')")

    # 2. Convertir format local CI (0XXXXXXXXX, 10 chiffres) → E.164 (+2250XXXXXXXXX)
    # IMPORTANT: on concatène +225 AVEC le 0 initial (format CI: +2250XXXXXXXXX, 14 chars).
    # Ne pas utiliser substring(from 2) qui stripperait le 0.
    op.execute(
        "UPDATE users SET phone_number = '+225' || phone_number "
        "WHERE phone_number ~ '^0\\d{9}$'"
    )

    # 3. Résoudre les doublons : garder le plus ancien, assigner un placeholder E.164 valide
    #    (+1XXXXXXXXXX, dérivé de l'UUID pour être stable et unique)
    op.execute("""
        UPDATE users u
        SET phone_number = '+1' || LPAD(
            (abs(hashtext(u.id::text)) % 9000000000 + 1000000000)::text,
            10, '0'
        )
        FROM (
            SELECT id
            FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY phone_number ORDER BY created_at) AS rn
                FROM users
            ) sub
            WHERE rn > 1
        ) dups
        WHERE u.id = dups.id
    """)

    # --- Modifications de schéma ---

    # Rendre email nullable
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=255), nullable=True)

    # Supprimer anciens index/contrainte sur email (nommés idx_ dans migration initiale)
    op.drop_index("idx_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")

    # Recréer index unique sur email (NULL-friendly : plusieurs NULL autorisés)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Ajouter index unique sur phone_number
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)

    # Ajouter CheckConstraint format E.164 sur phone_number
    op.create_check_constraint(
        "chk_users_phone_e164",
        "users",
        r"phone_number ~ '^\+[1-9]\d{6,14}$'",
    )


def downgrade() -> None:
    op.drop_constraint("chk_users_phone_e164", "users", type_="check")
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_index("ix_users_email", table_name="users")

    # Recréer anciens index/contrainte email
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("idx_users_email", "users", ["email"], unique=False)

    # Remettre email NOT NULL (requiert que toutes les lignes aient un email)
    op.alter_column("users", "email", existing_type=sa.VARCHAR(length=255), nullable=False)
