"""Routes du module catalog."""

from typing import Literal
from uuid import UUID

import structlog
from fastapi import APIRouter, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import TenantDbSession
from app.core.dependencies import CurrentStoreId, CurrentUserId
from app.core.exceptions import AppError
from app.core.pagination import CursorPage
from app.modules.catalog.bulk_import import (
    build_csv_template,
    build_xlsx_template,
    parse_bulk_import_file,
)
from app.modules.catalog.schemas import (
    ProductBulkCreateRequest,
    ProductBulkCreateResponse,
    ProductBulkItemResult,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.modules.catalog.service import ProductService
from app.modules.inventory.service import InventoryService

router = APIRouter()
logger = structlog.get_logger()


async def _create_bulk_item(
    db: AsyncSession, store_id: UUID, user_id: UUID, index: int, item: ProductCreate
) -> ProductBulkItemResult:
    """Crée un produit dans son propre SAVEPOINT ; ne relance jamais.

    Réutilisé par l'import JSON (`POST /bulk`) et l'import fichier (`POST /bulk/file`).
    """
    try:
        async with db.begin_nested():
            product = await ProductService(db).create_product(store_id, item)
            if item.current_stock is not None:
                await InventoryService(db).record_catalog_update(
                    store_id, product.id, item.current_stock, user_id
                )
        return ProductBulkItemResult(
            index=index, status="created", product=ProductResponse.model_validate(product)
        )
    except AppError as exc:
        return ProductBulkItemResult(
            index=index, status="failed", error=exc.message, field=exc.field
        )
    except Exception as exc:
        logger.warning("bulk_product_import_item_failed", index=index, error=str(exc))
        return ProductBulkItemResult(index=index, status="failed", error=str(exc))


def _build_bulk_response(results: list[ProductBulkItemResult]) -> ProductBulkCreateResponse:
    created_count = sum(1 for r in results if r.status == "created")
    return ProductBulkCreateResponse(
        processed=len(results),
        created_count=created_count,
        failed_count=len(results) - created_count,
        results=results,
    )


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
    low_stock_only: bool = Query(
        False, description="Ne retourner que les produits sous leur seuil de réapprovisionnement"
    ),
) -> CursorPage[ProductResponse]:
    """Liste paginée des produits actifs de la boutique."""
    return await ProductService(db).list_products(
        store_id=store_id,
        cursor=cursor,
        limit=limit,
        search=search,
        low_stock_only=low_stock_only,
    )


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
    user_id: CurrentUserId,
) -> ProductResponse:
    """Crée un nouveau produit dans le catalogue. 409 si le barcode est déjà utilisé."""
    product = await ProductService(db).create_product(store_id, payload)
    if payload.current_stock is not None:
        await InventoryService(db).record_catalog_update(
            store_id, product.id, payload.current_stock, user_id
        )
    return ProductResponse.model_validate(product)


@router.post(
    "/bulk",
    response_model=ProductBulkCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Import en masse de produits (migration depuis un système existant)",
)
async def create_products_bulk(
    payload: ProductBulkCreateRequest,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> ProductBulkCreateResponse:
    """Crée plusieurs produits en une fois, en best-effort ligne par ligne.

    Chaque item est traité dans son propre SAVEPOINT : une ligne en échec (barcode
    déjà pris, erreur inattendue) n'annule pas les autres. Toujours 200 ; le détail
    succès/échec est dans `results`. Un stock initial génère un mouvement tracé
    dans stock_movements, comme pour POST /products.
    """
    results = [
        await _create_bulk_item(db, store_id, user_id, index, item)
        for index, item in enumerate(payload.items)
    ]
    return _build_bulk_response(results)


@router.post(
    "/bulk/file",
    response_model=ProductBulkCreateResponse,
    status_code=status.HTTP_200_OK,
    summary="Import en masse de produits depuis un fichier CSV/Excel",
)
async def create_products_bulk_from_file(
    file: UploadFile,
    db: TenantDbSession,
    store_id: CurrentStoreId,
    user_id: CurrentUserId,
) -> ProductBulkCreateResponse:
    """Crée plusieurs produits à partir d'un fichier CSV ou Excel (.xlsx) exporté d'un
    système tiers. Détection automatique du séparateur CSV (`,`/`;`) et du format
    décimal (`.`/`,`) — courant sur les exports Excel en locale française.

    Tolérance ligne par ligne, y compris pour les erreurs de format : une ligne
    invalide est marquée `failed` sans annuler les autres. Voir aussi
    `GET /products/bulk/template` pour le format attendu.
    """
    content = await file.read()
    parsed_rows = parse_bulk_import_file(file.filename or "", content)

    results: list[ProductBulkItemResult] = []
    for index, product, error in parsed_rows:
        if product is None:
            results.append(ProductBulkItemResult(index=index, status="failed", error=error))
        else:
            results.append(await _create_bulk_item(db, store_id, user_id, index, product))

    return _build_bulk_response(results)


@router.get(
    "/bulk/template",
    summary="Télécharger un modèle de fichier pour l'import en masse",
)
async def download_bulk_import_template(
    _store_id: CurrentStoreId,
    format: Literal["csv", "xlsx"] = Query("csv"),
) -> Response:
    """Modèle vierge (en-têtes + 2 lignes d'exemple) au format attendu par
    `POST /products/bulk/file` : name, barcode, unit_price, current_stock.
    """
    if format == "xlsx":
        content = build_xlsx_template()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "template-import-produits.xlsx"
    else:
        content = build_csv_template()
        media_type = "text/csv"
        filename = "template-import-produits.csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
    user_id: CurrentUserId,
) -> ProductResponse:
    """Met à jour les champs fournis (PATCH partiel). 404 / 409 selon le cas."""
    product = await ProductService(db).update_product(product_id, store_id, payload)
    updates = payload.model_dump(exclude_unset=True)
    if "current_stock" in updates:
        await InventoryService(db).record_catalog_update(
            store_id, product_id, updates["current_stock"], user_id
        )
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
