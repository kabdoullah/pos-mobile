"""Routes du module catalog."""

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId
from app.core.pagination import CursorPage
from app.modules.catalog.schemas import ProductCreate, ProductResponse, ProductUpdate
from app.modules.catalog.service import ProductService

router = APIRouter()


@router.get(
    "",
    response_model=CursorPage[ProductResponse],
    summary="Lister les produits",
)
async def list_products(
    db: TenantDbSession,
    store_id: CurrentStoreId,
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
) -> CursorPage[ProductResponse]:
    """Liste paginée des produits actifs de la boutique."""
    return await ProductService(db).list_products(store_id=store_id, cursor=cursor, limit=limit, search=search)


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un produit",
)
async def create_product(
    payload: ProductCreate,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> ProductResponse:
    """Crée un nouveau produit dans le catalogue. 409 si le barcode est déjà utilisé."""
    product = await ProductService(db).create_product(store_id, payload)
    return ProductResponse.model_validate(product)


@router.get(
    "/by-barcode/{barcode}",
    response_model=ProductResponse,
    summary="Chercher par code-barres",
)
async def get_product_by_barcode(
    barcode: str,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> ProductResponse:
    """Retourne un produit par son code-barres. Utilisé lors du scan mobile."""
    product = await ProductService(db).get_by_barcode(barcode, store_id)
    return ProductResponse.model_validate(product)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Récupérer un produit",
)
async def get_product(
    product_id: UUID,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> ProductResponse:
    """Retourne un produit par son id."""
    product = await ProductService(db).get_by_id(product_id, store_id)
    return ProductResponse.model_validate(product)


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Mettre à jour un produit",
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> ProductResponse:
    """Met à jour les champs fournis (PATCH partiel). 404 / 409 selon le cas."""
    product = await ProductService(db).update_product(product_id, store_id, payload)
    return ProductResponse.model_validate(product)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprimer un produit",
)
async def delete_product(
    product_id: UUID,
    db: TenantDbSession,
    store_id: CurrentStoreId,
) -> None:
    """Supprime un produit (soft delete). Transparent pour le client."""
    await ProductService(db).delete_product(product_id, store_id)
