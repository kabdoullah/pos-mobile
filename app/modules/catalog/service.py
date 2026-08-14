"""Logique métier du module catalog."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import CursorPage, encode_cursor
from app.modules.catalog.models import Product
from app.modules.catalog.repository import ProductRepository
from app.modules.catalog.schemas import ProductCreate, ProductResponse, ProductUpdate


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
        product = Product(
            store_id=store_id,
            name=payload.name,
            barcode=payload.barcode,
            unit_price=payload.unit_price,
            current_stock=None,
            min_stock=payload.min_stock,
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
