"""account deletion: purge_store and scoped immutability exception.

Revision ID: e5b2c8d4f1a6
Revises: d1a4f7c2e9b0
Create Date: 2026-10-17

Suppression de compte depuis l'app (ADR-0011) :
- les fonctions d'immuabilité (sales, stock_movements, sale_returns,
  sale_return_items) laissent passer un DELETE uniquement si la ligne
  appartient à la boutique en cours de purge (app.purging_store_id, posé pour
  la transaction). UPDATE reste toujours interdit ;
- purge_store(p_store_id) : supprime la boutique et toutes ses données dans
  l'ordre des clés étrangères. SECURITY INVOKER : RLS s'applique, l'appelant
  doit avoir posé app.current_store_id sur la même boutique. Lève une
  exception si la boutique n'a pas été supprimée (invisible ou inexistante).

Aucune donnée existante n'est modifiée. Downgrade : restaure les fonctions
d'origine (texte de 0001, ebc43628c0d3, d1a4f7c2e9b0) et retire purge_store.

ATTENTION : SQL raw (fonctions plpgsql) non détecté par autogenerate.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b2c8d4f1a6"
down_revision: str | None = "d1a4f7c2e9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (fonction, arguments de RAISE EXCEPTION d'origine)
_IMMUTABILITY_FUNCTIONS = (
    ("prevent_sales_modification", "'sales table is immutable: % not allowed', TG_OP"),
    (
        "prevent_stock_movements_modification",
        "'stock_movements table is immutable: % not allowed', TG_OP",
    ),
    (
        "prevent_sale_returns_modification",
        "'% table is immutable: % not allowed', TG_TABLE_NAME, TG_OP",
    ),
)

# Ordre imposé par les clés étrangères (enfants avant parents).
_PURGE_TABLES = (
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


def _create_immutability_function(name: str, raise_args: str, *, allow_purge: bool) -> None:
    purge_exception = (
        """
            IF TG_OP = 'DELETE'
               AND OLD.store_id = NULLIF(current_setting('app.purging_store_id', true), '')::uuid
            THEN
                RETURN OLD;
            END IF;"""
        if allow_purge
        else ""
    )
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {name}()
        RETURNS TRIGGER AS $$
        BEGIN{purge_exception}
            RAISE EXCEPTION {raise_args}
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """)


def upgrade() -> None:
    for name, raise_args in _IMMUTABILITY_FUNCTIONS:
        _create_immutability_function(name, raise_args, allow_purge=True)

    deletes = "\n".join(
        f"            DELETE FROM {table} WHERE store_id = p_store_id;" for table in _PURGE_TABLES
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


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS purge_store(uuid);")
    for name, raise_args in _IMMUTABILITY_FUNCTIONS:
        _create_immutability_function(name, raise_args, allow_purge=False)
