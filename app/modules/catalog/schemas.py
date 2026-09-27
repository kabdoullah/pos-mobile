"""Schémas Pydantic du module catalog."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_BARCODE_PATTERN = r"^[A-Za-z0-9]{6,50}$"


class ProductCreate(BaseModel):
    """Payload de création d'un produit."""

    name: str = Field(..., min_length=1, max_length=255)
    barcode: str | None = Field(None, pattern=_BARCODE_PATTERN)
    unit_price: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    current_stock: int | None = Field(None, ge=0)
    min_stock: int | None = Field(None, ge=0)
    category_id: UUID | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v


class ProductUpdate(BaseModel):
    """Payload de mise à jour partielle d'un produit (PATCH)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    barcode: str | None = Field(None, pattern=_BARCODE_PATTERN)
    unit_price: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    current_stock: int | None = Field(None, ge=0)
    min_stock: int | None = Field(None, ge=0)
    # Absent = inchangé ; null = retire la catégorie (PATCH, exclude_unset).
    category_id: UUID | None = None

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v


class ProductResponse(BaseModel):
    """Représentation d'un produit en lecture."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    name: str
    barcode: str | None
    unit_price: Decimal
    current_stock: int | None
    min_stock: int | None
    category_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ProductBulkCreateRequest(BaseModel):
    """Payload d'import en masse (migration depuis un système existant)."""

    items: list[ProductCreate] = Field(..., min_length=1, max_length=500)


class ProductBulkItemResult(BaseModel):
    """Résultat de traitement d'une ligne de l'import en masse."""

    index: int
    status: Literal["created", "failed"]
    product: ProductResponse | None = None
    error: str | None = None
    field: str | None = None


class ProductBulkCreateResponse(BaseModel):
    """Résumé de l'import en masse : traitement best-effort, ligne par ligne."""

    processed: int
    created_count: int
    failed_count: int
    results: list[ProductBulkItemResult]


_CATEGORY_NAME_MAX = 60


def _strip(v: object) -> object:
    return v.strip() if isinstance(v, str) else v


class CategoryCreate(BaseModel):
    """Payload de création d'une catégorie."""

    name: str = Field(..., min_length=1, max_length=_CATEGORY_NAME_MAX)

    _strip_name = field_validator("name", mode="before")(_strip)


class CategoryUpdate(BaseModel):
    """Payload de renommage d'une catégorie."""

    name: str = Field(..., min_length=1, max_length=_CATEGORY_NAME_MAX)

    _strip_name = field_validator("name", mode="before")(_strip)


class CategoryResponse(BaseModel):
    """Représentation d'une catégorie en lecture."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
