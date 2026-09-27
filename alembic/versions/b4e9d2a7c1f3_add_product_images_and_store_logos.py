"""add product images and store logos.

Revision ID: b4e9d2a7c1f3
Revises: a8d3c1f0e2b4
Create Date: 2026-09-27

Stockage des images en PostgreSQL (BYTEA), voir ADR-0008 : le disque du
conteneur (Render) est éphémère, et les images profitent ainsi des backups et
de la RLS existants. Les images sont ré-encodées en WebP par l'API avant
insertion (pas de métadonnées EXIF).

- product_images : une image par produit (PK = product_id).
- store_logos : un logo par boutique (PK = store_id).
- products.image_version / stores.logo_version : SHA-256 de l'image courante
  (NULL sans image). Dénormalisé pour que la synchro d'état transporte la
  version sans jamais charger le binaire, et que changer d'image bumpe
  updated_at (propagation aux autres appareils via /sync/changes).

Aucune donnée existante n'est modifiée : colonnes nullables, tables vides.

ATTENTION : contient du SQL raw (RLS) non détecté par autogenerate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import BYTEA, UUID

# revision identifiers, used by Alembic.
revision: str = "b4e9d2a7c1f3"
down_revision: str | None = "a8d3c1f0e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TENANT_USING = "store_id = NULLIF(current_setting('app.current_store_id', true), '')::uuid"


def _image_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", BYTEA, nullable=False),
        sa.Column("content_type", sa.String(30), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    ]


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(f"""
        CREATE POLICY rls_{table}_tenant_isolation ON {table}
            USING ({_TENANT_USING})
            WITH CHECK ({_TENANT_USING});
    """)


def upgrade() -> None:
    # ============================================================
    # product_images
    # ============================================================
    op.create_table(
        "product_images",
        sa.Column("product_id", UUID(as_uuid=True), primary_key=True),
        *_image_columns(),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name="fk_product_images_product", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_product_images_store", ondelete="RESTRICT"
        ),
    )
    op.execute("CREATE INDEX idx_product_images_store ON product_images (store_id);")
    _enable_rls("product_images")

    # ============================================================
    # store_logos
    # ============================================================
    op.create_table(
        "store_logos",
        *_image_columns(),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"], name="fk_store_logos_store", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("store_id", name="pk_store_logos"),
    )
    _enable_rls("store_logos")

    # ============================================================
    # Versions dénormalisées
    # ============================================================
    op.add_column("products", sa.Column("image_version", sa.String(64), nullable=True))
    op.add_column("stores", sa.Column("logo_version", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("stores", "logo_version")
    op.drop_column("products", "image_version")

    for table in ("store_logos", "product_images"):
        op.execute(f"DROP POLICY IF EXISTS rls_{table}_tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(table)
