"""Schémas Pydantic du module returns (ADR-0010)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.sales.schemas import Amount

_CLOCK_DRIFT_SECONDS = 300


class ReturnReason(StrEnum):
    defective = "defective"
    damaged = "damaged"
    wrong_product = "wrong_product"
    sale_error = "sale_error"
    changed_mind = "changed_mind"
    other = "other"


class ItemCondition(StrEnum):
    """État de l'article rendu : seul `resellable` réintègre le stock."""

    resellable = "resellable"
    damaged = "damaged"
    defective = "defective"
    unsellable = "unsellable"


class RefundMethod(StrEnum):
    cash = "cash"
    mobile_money_orange = "mobile_money_orange"
    mobile_money_mtn = "mobile_money_mtn"
    mobile_money_wave = "mobile_money_wave"


class SaleReturnItemCreate(BaseModel):
    id: UUID
    sale_item_id: UUID
    quantity: int = Field(..., gt=0)
    condition: ItemCondition
    # Montant calculé par le client (voir refund.py) ; recalculé par le serveur.
    refund_amount: Amount


class SaleReturnCreate(BaseModel):
    id: UUID
    sale_id: UUID
    reason: ReturnReason
    note: str | None = Field(None, max_length=500)
    refund_method: RefundMethod
    refund_amount: Amount
    created_at: datetime
    items: list[SaleReturnItemCreate] = Field(..., min_length=1, max_length=100)

    @field_validator("note", mode="before")
    @classmethod
    def blank_note_is_none(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip() or None
        return v

    @model_validator(mode="after")
    def validate_return(self) -> "SaleReturnCreate":
        if self.reason == ReturnReason.other and self.note is None:
            raise ValueError("note is required when reason is 'other'")

        sale_item_ids = [item.sale_item_id for item in self.items]
        if len(set(sale_item_ids)) != len(sale_item_ids):
            raise ValueError("each sale_item_id may appear only once")
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("item ids must be unique")

        total = sum((item.refund_amount for item in self.items), Decimal("0"))
        if total != self.refund_amount:
            raise ValueError(f"refund_amount {self.refund_amount} != sum of items {total}")

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.created_at > datetime.now(UTC) + timedelta(seconds=_CLOCK_DRIFT_SECONDS):
            raise ValueError("created_at cannot be more than 5 minutes in the future")
        return self


class SaleReturnItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_return_id: UUID
    sale_item_id: UUID
    product_id: UUID | None
    quantity: int
    condition: str
    restocked: bool
    refund_amount: Decimal


class SaleReturnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    sale_id: UUID
    return_number: int | None
    reason: str
    note: str | None
    refund_method: str
    refund_amount: Decimal
    created_at: datetime
    created_by: UUID | None
    synced_at: datetime
    items: list[SaleReturnItemResponse]
