"""Accès aux données du module catalog."""

from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.images import ProcessedImage
from app.core.pagination import decode_cursor
from app.modules.catalog.models import Category, Product, ProductImage


class _CursorData(TypedDict):
    id: UUID
    created_at: datetime


def _parse_cursor(cursor: str) -> _CursorData | None:
    """Décode et valide un cursor opaque. Retourne None si invalide."""
    raw = decode_cursor(cursor)
    if raw is None:
        return None
    try:
        return _CursorData(
            id=UUID(str(raw["id"])),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )
    except (KeyError, ValueError):
        return None


class ProductRepository:
    """Repository pour l'entité Product."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_active_by_id(self, product_id: UUID, store_id: UUID) -> Product | None:
        """Retourne un produit actif par son id, ou None."""
        stmt = select(Product).where(
            Product.id == product_id,
            Product.store_id == store_id,
            Product.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_barcode(self, barcode: str, store_id: UUID) -> Product | None:
        """Retourne un produit actif par son code-barres, ou None."""
        stmt = select(Product).where(
            Product.barcode == barcode,
            Product.store_id == store_id,
            Product.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(
        self,
        store_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> tuple[list[Product], bool]:
        """Liste les produits actifs avec pagination cursor-based.

        Tri par (created_at DESC, id DESC). Retourne (items, has_more).
        """
        stmt = select(Product).where(Product.store_id == store_id, Product.deleted_at.is_(None))

        if search:
            stmt = stmt.where(Product.name.ilike(f"%{search}%"))

        if low_stock_only:
            stmt = stmt.where(
                Product.current_stock.isnot(None),
                Product.min_stock.isnot(None),
                Product.current_stock <= Product.min_stock,
            )

        if cursor:
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                stmt = stmt.where(
                    tuple_(Product.created_at, Product.id) < (parsed["created_at"], parsed["id"])
                )

        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc()).limit(limit + 1)

        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        return rows, has_more

    async def create(self, product: Product) -> Product:
        """Crée et persiste un produit."""
        self.db.add(product)
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def update(self, product: Product, updates: dict[str, Any]) -> Product:
        """Applique les champs fournis et persiste."""
        for field, value in updates.items():
            setattr(product, field, value)
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def adjust_stock(self, product: Product, delta: int, enable_tracking: bool) -> int | None:
        """Applique un delta sur current_stock.

        Si enable_tracking=True, active le suivi si le produit n'était pas encore
        suivi (NULL -> COALESCE(0) + delta). Si enable_tracking=False (vente), ne
        touche jamais un produit non suivi : current_stock reste NULL (choix
        délibéré du commerçant de ne pas suivre ce produit).
        Pas de garde-fou de non-négativité : le stock peut aller sous zéro.

        Lost update possible sous écriture concurrente sur le même produit (pas de
        FOR UPDATE) : accepté, décision produit actée (le stock ne bloque jamais
        une vente, un léger désynchronisme n'est pas une violation d'invariant).
        """
        if product.current_stock is None:
            if not enable_tracking:
                return None
            product.current_stock = delta
        else:
            product.current_stock = product.current_stock + delta
        await self.db.flush()
        await self.db.refresh(product)
        return product.current_stock

    async def set_stock_null(self, product: Product) -> None:
        """Désactive le tracking du stock (current_stock -> NULL)."""
        product.current_stock = None
        await self.db.flush()
        await self.db.refresh(product)

    async def soft_delete(self, product: Product) -> None:
        """Marque le produit comme supprimé (soft delete)."""
        product.deleted_at = datetime.now(UTC)
        await self.db.flush()

    async def get_by_id_including_deleted(self, product_id: UUID) -> Product | None:
        """Retourne un produit par son id, deleted ou non."""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_barcode_excluding(
        self, barcode: str, exclude_id: UUID
    ) -> Product | None:
        """Retourne un produit actif avec ce barcode, en excluant un id donné."""
        stmt = select(Product).where(
            Product.barcode == barcode,
            Product.deleted_at.is_(None),
            Product.id != exclude_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()


class CategoryRepository:
    """Accès aux catégories. Filtrage tenant assuré par RLS + store_id explicite."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_active(self, store_id: UUID) -> list[Category]:
        """Catégories non supprimées, triées par nom (insensible à la casse)."""
        stmt = (
            select(Category)
            .where(Category.store_id == store_id, Category.deleted_at.is_(None))
            .order_by(func.lower(Category.name))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_id(self, category_id: UUID, store_id: UUID) -> Category | None:
        """Catégorie non supprimée de la boutique, ou None."""
        stmt = select(Category).where(
            Category.id == category_id,
            Category.store_id == store_id,
            Category.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_including_deleted(self, category_id: UUID) -> Category | None:
        """Catégorie par id, supprimée ou non (RLS limite à la boutique courante)."""
        result = await self.db.execute(select(Category).where(Category.id == category_id))
        return result.scalar_one_or_none()

    async def get_active_by_name_excluding(
        self, name: str, store_id: UUID, exclude_id: UUID | None
    ) -> Category | None:
        """Autre catégorie active portant ce nom (insensible à la casse), ou None."""
        stmt = select(Category).where(
            Category.store_id == store_id,
            Category.deleted_at.is_(None),
            func.lower(Category.name) == name.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, category: Category) -> Category:
        """Crée et persiste une catégorie."""
        self.db.add(category)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def update(self, category: Category, updates: dict[str, Any]) -> Category:
        """Applique les champs fournis et persiste."""
        for field, value in updates.items():
            setattr(category, field, value)
        await self.db.flush()
        await self.db.refresh(category)
        return category

    async def soft_delete_and_detach_products(self, category: Category) -> None:
        """Supprime la catégorie (soft) et retire le lien de ses produits.

        Le trigger updated_at des produits bumpe leur date : les autres appareils
        récupèrent la correction au prochain pull.
        """
        category.deleted_at = datetime.now(UTC)
        # Via l'ORM (et non un UPDATE en masse) : les produits déjà chargés dans
        # la session restent cohérents. Le refresh relit le updated_at posé par
        # le trigger (pas de chargement implicite possible en async).
        result = await self.db.execute(
            select(Product).where(
                Product.category_id == category.id, Product.store_id == category.store_id
            )
        )
        products = list(result.scalars().all())
        for product in products:
            product.category_id = None
        await self.db.flush()
        for product in products:
            await self.db.refresh(product)


class ProductImageRepository:
    """Images produit. Ne charge le binaire que pour le servir."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, product_id: UUID) -> ProductImage | None:
        """Image du produit (RLS : boutique courante uniquement), ou None."""
        return await self.db.get(ProductImage, product_id)

    async def upsert(self, product: Product, image: ProcessedImage) -> Product:
        """Remplace l'image du produit et met à jour sa version (bumpe updated_at)."""
        row = await self.get(product.id)
        if row is None:
            row = ProductImage(product_id=product.id, store_id=product.store_id)
            self.db.add(row)
        row.content = image.content
        row.content_type = image.content_type
        row.width = image.width
        row.height = image.height
        row.sha256 = image.sha256
        product.image_version = image.sha256
        await self.db.flush()
        await self.db.refresh(product)
        return product

    async def delete(self, product: Product) -> Product:
        """Supprime l'image du produit (sans erreur s'il n'en a pas)."""
        row = await self.get(product.id)
        if row is not None:
            await self.db.delete(row)
        product.image_version = None
        await self.db.flush()
        await self.db.refresh(product)
        return product
