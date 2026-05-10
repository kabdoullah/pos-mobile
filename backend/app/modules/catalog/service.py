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

    async def get_by_id(self, product_id: UUID) -> Product:
        """Retourne un produit actif ou lève NotFoundError."""
        product = await self.repo.get_active_by_id(product_id)
        if product is None:
            raise NotFoundError("Product not found.")
        return product

    async def get_by_barcode(self, barcode: str) -> Product:
        """Retourne un produit actif par barcode ou lève NotFoundError."""
        product = await self.repo.get_active_by_barcode(barcode)
        if product is None:
            raise NotFoundError("Product not found.")
        return product

    async def list_products(
        self,
        cursor: str | None,
        limit: int,
        search: str | None,
    ) -> CursorPage[ProductResponse]:
        """Liste paginée des produits actifs de la boutique."""
        rows, has_more = await self.repo.list_active(cursor=cursor, limit=limit, search=search)
        items = [ProductResponse.model_validate(p) for p in rows]
        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(
                {"id": str(last.id), "created_at": last.created_at.isoformat()}
            )
        return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

    async def create_product(self, store_id: UUID, payload: ProductCreate) -> Product:
        """Crée un produit. ConflictError si le barcode est déjà utilisé."""
        if payload.barcode is not None:
            existing = await self.repo.get_active_by_barcode(payload.barcode)
            if existing is not None:
                raise ConflictError("A product with this barcode already exists.", field="barcode")
        product = Product(
            store_id=store_id,
            name=payload.name,
            barcode=payload.barcode,
            unit_price=payload.unit_price,
            current_stock=payload.current_stock,
        )
        return await self.repo.create(product)

    async def update_product(self, product_id: UUID, payload: ProductUpdate) -> Product:
        """Met à jour les champs fournis (PATCH). ConflictError si nouveau barcode déjà pris."""
        product = await self.get_by_id(product_id)
        updates = payload.model_dump(exclude_unset=True)
        new_barcode = updates.get("barcode")
        if new_barcode is not None and new_barcode != product.barcode:
            existing = await self.repo.get_active_by_barcode(new_barcode)
            if existing is not None:
                raise ConflictError("A product with this barcode already exists.", field="barcode")
        return await self.repo.update(product, updates)

    async def delete_product(self, product_id: UUID) -> None:
        """Soft delete d'un produit. NotFoundError si absent."""
        product = await self.get_by_id(product_id)
        await self.repo.soft_delete(product)
