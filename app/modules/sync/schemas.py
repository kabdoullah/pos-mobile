"""Schémas Pydantic du module sync."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.modules.catalog.schemas import CategoryResponse, ProductResponse
from app.modules.sales.schemas import SaleCreate, SaleResponse

_BARCODE_PATTERN = r"^[A-Za-z0-9]{6,50}$"


class SaleSyncResultStatus(StrEnum):
    created = "created"
    already_exists = "already_exists"
    failed = "failed"


class SaleSyncResult(BaseModel):
    id: UUID
    status: SaleSyncResultStatus
    receipt_number: int | None = None
    error: str | None = None


class SalesBatchSyncRequest(BaseModel):
    sales: list[SaleCreate] = Field(..., min_length=1, max_length=50)


class SalesBatchSyncResponse(BaseModel):
    processed: int
    results: list[SaleSyncResult]


class ProductSyncRequest(BaseModel):
    id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    barcode: str | None = Field(None, pattern=_BARCODE_PATTERN)
    # ADR-0009 : ex-unit_price, encore accepté des anciennes versions de l'app.
    selling_price: Decimal = Field(
        ...,
        ge=Decimal("0"),
        max_digits=12,
        decimal_places=2,
        validation_alias=AliasChoices("selling_price", "unit_price"),
    )
    # Absent (anciennes versions) = inchangé ; null = non renseigné.
    # Distingué via model_fields_set.
    purchase_price: Decimal | None = Field(None, ge=Decimal("0"), max_digits=12, decimal_places=2)
    current_stock: int | None = Field(None, ge=0)
    min_stock: int | None = Field(None, ge=0)
    # ADR-0008. Absent (anciennes versions de l'app) = catégorie inchangée ;
    # null = retire la catégorie. Distingué via model_fields_set.
    category_id: UUID | None = None
    client_updated_at: datetime
    deleted: bool = False

    @field_validator("client_updated_at", mode="after")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("client_updated_at must be timezone-aware")
        return v


class ProductSyncStatus(StrEnum):
    created = "created"
    updated = "updated"
    no_change = "no_change"
    conflict = "conflict"
    deleted = "deleted"


class ProductSyncResponse(BaseModel):
    id: UUID
    status: ProductSyncStatus
    server_state: ProductResponse | None = None


class CategorySyncRequest(BaseModel):
    """État complet d'une catégorie envoyé par le client (last-write-wins)."""

    id: UUID
    name: str = Field(..., min_length=1, max_length=60)
    client_updated_at: datetime
    deleted: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    @field_validator("client_updated_at", mode="after")
    @classmethod
    def require_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("client_updated_at must be timezone-aware")
        return v


class CategorySyncResponse(BaseModel):
    """Résultat de la synchro d'une catégorie (mêmes statuts que les produits)."""

    id: UUID
    status: ProductSyncStatus
    server_state: CategoryResponse | None = None


class SyncChangesResponse(BaseModel):
    # Par défaut vide : compatible avec les clients qui ignorent ce champ.
    categories: list[CategoryResponse] = []
    products: list[ProductResponse]
    sales: list[SaleResponse]
    next_cursor: str | None = None
    has_more: bool
    server_time: datetime
