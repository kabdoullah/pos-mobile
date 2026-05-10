"""Schémas Pydantic du module catalog."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_BARCODE_PATTERN = r"^[A-Za-z0-9]{6,50}$"


class ProductCreate(BaseModel):
    """Payload de création d'un produit."""

    name: str = Field(..., min_length=1, max_length=255)
    barcode: str | None = Field(None, pattern=_BARCODE_PATTERN)
    unit_price: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    current_stock: int | None = Field(None, ge=0)

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
    created_at: datetime
    updated_at: datetime
