"""Logique métier du module catalog."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.images import PRODUCT_IMAGE_MAX_SIDE, normalize_image
from app.core.pagination import CursorPage, encode_cursor
from app.modules.catalog.models import Category, Product, ProductImage
from app.modules.catalog.repository import (
    CategoryRepository,
    ProductImageRepository,
    ProductRepository,
)
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryUpdate,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)


class ProductService:
    """Service métier de la gestion du catalogue produits."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = ProductRepository(db)

    async def get_by_id(self, product_id: UUID, store_id: UUID) -> Product:
        """Retourne un produit actif ou lève NotFoundError."""
        product = await self.repo.get_active_by_id(product_id, store_id)
        if product is None:
            raise NotFoundError("Product not found.")
        return product

    async def get_by_barcode(self, barcode: str, store_id: UUID) -> Product:
        """Retourne un produit actif par barcode ou lève NotFoundError."""
        product = await self.repo.get_active_by_barcode(barcode, store_id)
        if product is None:
            raise NotFoundError("Product not found.")
        return product

    async def list_products(
        self,
        store_id: UUID,
        cursor: str | None,
        limit: int,
        search: str | None,
        low_stock_only: bool = False,
    ) -> CursorPage[ProductResponse]:
        """Liste paginée des produits actifs de la boutique."""
        rows, has_more = await self.repo.list_active(
            store_id=store_id,
            cursor=cursor,
            limit=limit,
            search=search,
            low_stock_only=low_stock_only,
        )
        items = [ProductResponse.model_validate(p) for p in rows]
        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(
                {"id": str(last.id), "created_at": last.created_at.isoformat()}
            )
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def create_product(self, store_id: UUID, payload: ProductCreate) -> Product:
        """Crée un produit. ConflictError si le barcode est déjà utilisé.

        current_stock n'est jamais posé directement à la création : il reste NULL
        (non suivi) et le stock initial, si fourni, est appliqué par l'appelant
        (router) via InventoryService.record_catalog_update pour être tracé.
        """
        if payload.barcode is not None:
            existing = await self.repo.get_active_by_barcode(payload.barcode, store_id)
            if existing is not None:
                raise ConflictError("A product with this barcode already exists.", field="barcode")
        category_id = await CategoryService(self.db).resolve_for_product(
            store_id, payload.category_id
        )
        product = Product(
            store_id=store_id,
            name=payload.name,
            barcode=payload.barcode,
            selling_price=payload.selling_price,
            purchase_price=payload.purchase_price,
            current_stock=None,
            min_stock=payload.min_stock,
            category_id=category_id,
        )
        return await self.repo.create(product)

    async def update_product(
        self, product_id: UUID, store_id: UUID, payload: ProductUpdate
    ) -> Product:
        """Met à jour les champs fournis (PATCH). ConflictError si nouveau barcode déjà pris.

        current_stock est volontairement retiré des updates génériques : sa modification
        passe exclusivement par apply_stock_delta/disable_stock_tracking, orchestré par
        l'appelant (router) via InventoryService pour garantir la traçabilité.
        """
        product = await self.get_by_id(product_id, store_id)
        updates = payload.model_dump(exclude_unset=True)
        updates.pop("current_stock", None)
        new_barcode = updates.get("barcode")
        if new_barcode is not None and new_barcode != product.barcode:
            existing = await self.repo.get_active_by_barcode(new_barcode, store_id)
            if existing is not None:
                raise ConflictError("A product with this barcode already exists.", field="barcode")
        if "category_id" in updates:
            updates["category_id"] = await CategoryService(self.db).resolve_for_product(
                store_id, updates["category_id"]
            )
        return await self.repo.update(product, updates)

    async def apply_stock_delta(
        self, product_id: UUID, store_id: UUID, delta: int, enable_tracking: bool
    ) -> Product:
        """Applique un delta atomique sur current_stock. NotFoundError si absent."""
        product = await self.get_by_id(product_id, store_id)
        await self.repo.adjust_stock(product, delta, enable_tracking)
        return product

    async def disable_stock_tracking(self, product_id: UUID, store_id: UUID) -> Product:
        """Désactive le tracking du stock (current_stock -> NULL). NotFoundError si absent."""
        product = await self.get_by_id(product_id, store_id)
        await self.repo.set_stock_null(product)
        return product

    async def delete_product(self, product_id: UUID, store_id: UUID) -> None:
        """Soft delete d'un produit. NotFoundError si absent."""
        product = await self.get_by_id(product_id, store_id)
        await self.repo.soft_delete(product)

    async def set_image(self, product_id: UUID, store_id: UUID, raw: bytes) -> Product:
        """Normalise l'image (WebP 512 px, sans EXIF) et la rattache au produit.

        413 au-delà de 5 Mo, 422 si ce n'est pas une image JPEG/PNG/WebP.
        """
        product = await self.get_by_id(product_id, store_id)
        image = normalize_image(
            raw, max_width=PRODUCT_IMAGE_MAX_SIDE, max_height=PRODUCT_IMAGE_MAX_SIDE
        )
        return await ProductImageRepository(self.db).upsert(product, image)

    async def get_image(self, product_id: UUID, store_id: UUID) -> ProductImage:
        """Image d'un produit actif, ou NotFoundError."""
        await self.get_by_id(product_id, store_id)
        image = await ProductImageRepository(self.db).get(product_id)
        if image is None:
            raise NotFoundError("Product image not found.")
        return image

    async def delete_image(self, product_id: UUID, store_id: UUID) -> Product:
        """Retire l'image d'un produit actif."""
        product = await self.get_by_id(product_id, store_id)
        return await ProductImageRepository(self.db).delete(product)


class CategoryService:
    """Service métier des catégories de produits (ADR-0008)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CategoryRepository(db)

    async def list_categories(self, store_id: UUID) -> list[Category]:
        """Catégories actives de la boutique, par nom."""
        return await self.repo.list_active(store_id)

    async def get_by_id(self, category_id: UUID, store_id: UUID) -> Category:
        """Catégorie active ou NotFoundError."""
        category = await self.repo.get_active_by_id(category_id, store_id)
        if category is None:
            raise NotFoundError("Category not found.")
        return category

    async def _ensure_name_available(
        self, name: str, store_id: UUID, exclude_id: UUID | None
    ) -> None:
        existing = await self.repo.get_active_by_name_excluding(name, store_id, exclude_id)
        if existing is not None:
            raise ConflictError("A category with this name already exists.", field="name")

    async def create_category(self, store_id: UUID, payload: CategoryCreate) -> Category:
        """Crée une catégorie. ConflictError si le nom existe déjà (casse ignorée)."""
        await self._ensure_name_available(payload.name, store_id, None)
        return await self.repo.create(Category(store_id=store_id, name=payload.name))

    async def rename_category(
        self, category_id: UUID, store_id: UUID, payload: CategoryUpdate
    ) -> Category:
        """Renomme une catégorie. ConflictError si le nom est déjà pris."""
        category = await self.get_by_id(category_id, store_id)
        await self._ensure_name_available(payload.name, store_id, category.id)
        return await self.repo.update(category, {"name": payload.name})

    async def delete_category(self, category_id: UUID, store_id: UUID) -> None:
        """Supprime (soft) la catégorie et détache ses produits."""
        category = await self.get_by_id(category_id, store_id)
        await self.repo.soft_delete_and_detach_products(category)

    async def resolve_for_product(self, store_id: UUID, category_id: UUID | None) -> UUID | None:
        """Valide la catégorie d'un produit.

        - `None` : pas de catégorie.
        - catégorie supprimée : `None` (la suppression l'emporte, même règle que
          le détachement des produits).
        - catégorie inconnue de la boutique (inexistante, ou d'une autre
          boutique, invisible via RLS) : ValidationError (422).
        """
        if category_id is None:
            return None
        category = await self.repo.get_by_id_including_deleted(category_id)
        if category is None or category.store_id != store_id:
            raise ValidationError("Unknown category.", field="category_id")
        if category.deleted_at is not None:
            return None
        return category.id
