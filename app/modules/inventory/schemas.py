"""Schémas Pydantic du module inventory."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StockMovementReason(StrEnum):
    sale = "sale"
    manual_adjustment = "manual_adjustment"
    catalog_update = "catalog_update"


class ManualStockAdjustmentCreate(BaseModel):
    """Payload d'ajustement manuel du stock (réception, casse, correction d'inventaire)."""

    product_id: UUID
    quantity_delta: int
    note: str | None = Field(None, max_length=500)

    @field_validator("quantity_delta")
    @classmethod
    def reject_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("quantity_delta must not be zero")
        return v


class StockMovementResponse(BaseModel):
    """Représentation d'un mouvement de stock en lecture."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    product_id: UUID
    quantity_delta: int | None
    reason: StockMovementReason
    resulting_stock: int | None
    sale_id: UUID | None
    created_by: UUID | None
    note: str | None
    created_at: datetime
