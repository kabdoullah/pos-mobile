"""Initial schema with users, stores, products, sales, sale_items.

Cette migration crée le schéma initial complet du backend POS Mobile CI :
- Extensions PostgreSQL (pgcrypto, pg_trgm)
- Type ENUM payment_method_enum
- Fonction trigger update_updated_at_column
- Tables : users, email_verification_tokens, password_reset_tokens, stores,
          products, sales, sale_items
- Indexes (~15)
- Politiques RLS sur les tables tenant
- Triggers : updated_at, immuabilité de sales, génération de receipt_number

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-29

Voir docs/data-model-detailed.md pour la justification de chaque choix.

ATTENTION : cette migration contient du SQL raw (RLS, triggers) qui n'est PAS
détecté par alembic autogenerate. Toute modification ultérieure de ce SQL doit
être faite manuellement dans une nouvelle migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM, UUID

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============================================================
    # Extensions
    # ============================================================
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')

    # ============================================================
    # Type ENUM
    # ============================================================
    payment_method_enum = ENUM(
        "cash",
        "mobile_money_orange",
        "mobile_money_mtn",
        "mobile_money_wave",
        "mixed",
        name="payment_method_enum",
        create_type=True,
    )
    payment_method_enum.create(op.get_bind(), checkfirst=False)

    # ============================================================
    # Fonction trigger : updated_at automatique
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table users
    # ============================================================
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint("email = LOWER(email)", name="chk_users_email_lowercase"),
        sa.CheckConstraint(
            r"email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'",
            name="chk_users_email_format",
        ),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.execute("COMMENT ON COLUMN users.password_hash IS 'bcrypt hash, cost factor 12';")
    op.execute("COMMENT ON COLUMN users.email_verified_at IS 'NULL = email pas encore confirmé';")

    op.execute("""
        CREATE TRIGGER trg_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # ============================================================
    # Tables tokens
    # ============================================================
    for table_name in ("email_verification_tokens", "password_reset_tokens"):
        op.create_table(
            table_name,
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(
                ["user_id"], ["users.id"],
                name=f"fk_{table_name}_user", ondelete="CASCADE",
            ),
            sa.UniqueConstraint("token_hash", name=f"uq_{table_name}_hash"),
        )
        op.create_index(f"idx_{table_name}_user_id", table_name, ["user_id"])
        op.create_index(f"idx_{table_name}_expires_at", table_name, ["expires_at"])

    # ============================================================
    # Table stores
    # ============================================================
    op.create_table(
        "stores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("ncc", sa.String(20), nullable=True),
        sa.Column("vat_subject", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("receipt_footer_text", sa.String(200), nullable=True),
        sa.Column("next_receipt_number", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"],
            name="fk_stores_owner", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("owner_id", name="uq_stores_owner"),
        sa.CheckConstraint(
            "ncc IS NULL OR (length(ncc) BETWEEN 7 AND 13)",
            name="chk_stores_ncc_format",
        ),
        sa.CheckConstraint("next_receipt_number >= 1", name="chk_stores_next_receipt_number"),
    )
    op.create_index("idx_stores_owner_id", "stores", ["owner_id"])
    op.execute("COMMENT ON COLUMN stores.owner_id IS '1 boutique par utilisateur au MVP';")
    op.execute("COMMENT ON COLUMN stores.ncc IS 'Numéro de Compte Contribuable DGI, optionnel';")
    op.execute("COMMENT ON COLUMN stores.next_receipt_number IS 'Compteur du prochain reçu pour cette boutique';")

    op.execute("""
        CREATE TRIGGER trg_stores_updated_at
            BEFORE UPDATE ON stores
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # RLS sur stores
    op.execute("ALTER TABLE stores ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_stores_self_access ON stores
            USING (id = current_setting('app.current_store_id', true)::uuid)
            WITH CHECK (id = current_setting('app.current_store_id', true)::uuid);
    """)

    # ============================================================
    # Table products
    # ============================================================
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("barcode", sa.String(50), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_stock", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"],
            name="fk_products_store", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("unit_price >= 0", name="chk_products_unit_price_positive"),
        sa.CheckConstraint(
            "current_stock IS NULL OR current_stock >= 0",
            name="chk_products_current_stock_non_negative",
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="chk_products_name_not_empty"),
    )

    # Index partiels pour les produits actifs uniquement
    op.execute("""
        CREATE INDEX idx_products_store_name ON products (store_id, name)
            WHERE deleted_at IS NULL;
    """)
    op.execute("""
        CREATE INDEX idx_products_store_barcode ON products (store_id, barcode)
            WHERE barcode IS NOT NULL AND deleted_at IS NULL;
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_products_store_barcode_active
            ON products (store_id, barcode)
            WHERE barcode IS NOT NULL AND deleted_at IS NULL;
    """)

    op.execute("COMMENT ON COLUMN products.current_stock IS 'NULL = stock non géré';")
    op.execute("COMMENT ON COLUMN products.unit_price IS 'Prix en FCFA, NUMERIC(12,2) pour précision';")
    op.execute("COMMENT ON COLUMN products.deleted_at IS 'Soft delete : NULL = actif';")

    op.execute("""
        CREATE TRIGGER trg_products_updated_at
            BEFORE UPDATE ON products
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    """)

    # RLS sur products
    op.execute("ALTER TABLE products ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_products_tenant_isolation ON products
            USING (store_id = current_setting('app.current_store_id', true)::uuid)
            WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);
    """)

    # ============================================================
    # Fonction de génération atomique du receipt_number
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION generate_receipt_number()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.receipt_number IS NOT NULL AND NEW.receipt_number > 0 THEN
                RETURN NEW;
            END IF;

            UPDATE stores
            SET next_receipt_number = next_receipt_number + 1
            WHERE id = NEW.store_id
            RETURNING next_receipt_number - 1 INTO NEW.receipt_number;

            IF NEW.receipt_number IS NULL THEN
                RAISE EXCEPTION 'Could not generate receipt_number for store_id %', NEW.store_id;
            END IF;

            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Fonction d'immuabilité de sales
    # ============================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_sales_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'sales table is immutable: % not allowed', TG_OP
                USING ERRCODE = 'feature_not_supported';
        END;
        $$ language 'plpgsql';
    """)

    # ============================================================
    # Table sales (immuable)
    # ============================================================
    op.create_table(
        "sales",
        # Pas de DEFAULT sur id : généré côté client pour idempotence sync
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        # receipt_number nullable au moment de l'INSERT, le trigger le remplit
        sa.Column("receipt_number", sa.Integer, nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "payment_method",
            ENUM(
                "cash", "mobile_money_orange", "mobile_money_mtn",
                "mobile_money_wave", "mixed",
                name="payment_method_enum", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("cash_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("mobile_money_amount", sa.Numeric(12, 2), nullable=True),
        # Pas de DEFAULT : timestamp côté client
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"],
            name="fk_sales_store", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("store_id", "receipt_number", name="uq_sales_store_receipt_number"),
        sa.CheckConstraint("total_amount >= 0 AND vat_amount >= 0", name="chk_sales_amounts_positive"),
        sa.CheckConstraint("vat_amount <= total_amount", name="chk_sales_vat_lte_total"),
        sa.CheckConstraint(
            "(payment_method = 'mixed' AND cash_amount IS NOT NULL AND mobile_money_amount IS NOT NULL) "
            "OR (payment_method != 'mixed' AND (cash_amount IS NULL OR mobile_money_amount IS NULL))",
            name="chk_sales_mixed_amounts",
        ),
        sa.CheckConstraint(
            "payment_method != 'mixed' "
            "OR (COALESCE(cash_amount, 0) + COALESCE(mobile_money_amount, 0) = total_amount)",
            name="chk_sales_mixed_sum_equals_total",
        ),
        sa.CheckConstraint(
            "receipt_number IS NULL OR receipt_number >= 1",
            name="chk_sales_receipt_number_positive",
        ),
    )

    op.execute("""
        CREATE INDEX idx_sales_store_created_at ON sales (store_id, created_at DESC);
    """)
    op.create_index("idx_sales_store_receipt_number", "sales", ["store_id", "receipt_number"])

    op.execute("COMMENT ON TABLE sales IS 'Table immuable. Aucun UPDATE/DELETE autorisé.';")
    op.execute("COMMENT ON COLUMN sales.id IS 'UUID v4 généré côté client pour idempotence sync';")
    op.execute("COMMENT ON COLUMN sales.receipt_number IS 'Généré par trigger generate_receipt_number';")
    op.execute("COMMENT ON COLUMN sales.created_at IS 'Timestamp côté client au moment de la vente';")
    op.execute("COMMENT ON COLUMN sales.synced_at IS 'Timestamp serveur, sert au pull /sync/changes';")

    # Triggers
    op.execute("""
        CREATE TRIGGER trg_sales_receipt_number
            BEFORE INSERT ON sales
            FOR EACH ROW
            EXECUTE FUNCTION generate_receipt_number();
    """)
    op.execute("""
        CREATE TRIGGER trg_sales_immutable_update
            BEFORE UPDATE ON sales
            FOR EACH ROW
            EXECUTE FUNCTION prevent_sales_modification();
    """)
    op.execute("""
        CREATE TRIGGER trg_sales_immutable_delete
            BEFORE DELETE ON sales
            FOR EACH ROW
            EXECUTE FUNCTION prevent_sales_modification();
    """)

    # RLS sur sales
    op.execute("ALTER TABLE sales ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_sales_tenant_isolation ON sales
            USING (store_id = current_setting('app.current_store_id', true)::uuid)
            WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);
    """)

    # Maintenant que les triggers sont en place, on peut rendre receipt_number NOT NULL
    # via un check après insertion (on garde nullable au niveau colonne car le trigger
    # le remplit pendant le BEFORE INSERT)

    # ============================================================
    # Table sale_items
    # ============================================================
    op.create_table(
        "sale_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sale_id", UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=True),
        sa.Column("product_name_at_sale", sa.String(255), nullable=False),
        sa.Column("unit_price_at_sale", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"],
            name="fk_sale_items_sale", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"], ["stores.id"],
            name="fk_sale_items_store", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"],
            name="fk_sale_items_product", ondelete="SET NULL",
        ),
        sa.CheckConstraint("quantity > 0", name="chk_sale_items_quantity_positive"),
        sa.CheckConstraint("unit_price_at_sale >= 0", name="chk_sale_items_unit_price_positive"),
        sa.CheckConstraint(
            "line_total = unit_price_at_sale * quantity",
            name="chk_sale_items_line_total",
        ),
    )

    op.create_index("idx_sale_items_sale_id", "sale_items", ["sale_id"])
    op.create_index("idx_sale_items_store_id", "sale_items", ["store_id"])
    op.execute("""
        CREATE INDEX idx_sale_items_product_id ON sale_items (product_id)
            WHERE product_id IS NOT NULL;
    """)

    op.execute("COMMENT ON COLUMN sale_items.product_id IS 'NULL si produit hard-deleted';")
    op.execute("COMMENT ON COLUMN sale_items.store_id IS 'Dénormalisé pour le RLS';")
    op.execute("COMMENT ON COLUMN sale_items.product_name_at_sale IS 'Copie immuable du nom au moment de la vente';")

    # RLS sur sale_items
    op.execute("ALTER TABLE sale_items ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY rls_sale_items_tenant_isolation ON sale_items
            USING (store_id = current_setting('app.current_store_id', true)::uuid)
            WITH CHECK (store_id = current_setting('app.current_store_id', true)::uuid);
    """)


def downgrade() -> None:
    # ============================================================
    # Drop dans l'ordre inverse pour respecter les FK
    # ============================================================

    # Tables tenant
    op.drop_table("sale_items")

    # Sales : drop des triggers d'abord (sinon le DROP TABLE va déclencher
    # le trigger d'immuabilité)
    op.execute("DROP TRIGGER IF EXISTS trg_sales_immutable_delete ON sales;")
    op.execute("DROP TRIGGER IF EXISTS trg_sales_immutable_update ON sales;")
    op.execute("DROP TRIGGER IF EXISTS trg_sales_receipt_number ON sales;")
    op.drop_table("sales")

    op.execute("DROP TRIGGER IF EXISTS trg_products_updated_at ON products;")
    op.drop_table("products")

    op.execute("DROP TRIGGER IF EXISTS trg_stores_updated_at ON stores;")
    op.drop_table("stores")

    # Tables hors-tenant
    op.drop_table("password_reset_tokens")
    op.drop_table("email_verification_tokens")

    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users;")
    op.drop_table("users")

    # Fonctions
    op.execute("DROP FUNCTION IF EXISTS prevent_sales_modification();")
    op.execute("DROP FUNCTION IF EXISTS generate_receipt_number();")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Type ENUM
    op.execute("DROP TYPE IF EXISTS payment_method_enum;")

    # Note : on ne drop PAS les extensions pgcrypto et pg_trgm car elles
    # peuvent être utilisées par d'autres applications sur la même DB.
