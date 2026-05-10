"""Schémas Pydantic du module sync."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.modules.catalog.schemas import ProductResponse
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
    unit_price: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    current_stock: int | None = Field(None, ge=0)
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


class SyncChangesResponse(BaseModel):
    products: list[ProductResponse]
    sales: list[SaleResponse]
    next_cursor: str | None = None
    has_more: bool
    server_time: datetime
