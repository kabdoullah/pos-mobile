"""Schémas Pydantic du module sales."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.pagination import CursorPage

_CLOCK_DRIFT_SECONDS = 300


class PaymentMethod(StrEnum):
    cash = "cash"
    mobile_money_orange = "mobile_money_orange"
    mobile_money_mtn = "mobile_money_mtn"
    mobile_money_wave = "mobile_money_wave"
    mixed = "mixed"


class SaleItemCreate(BaseModel):
    product_id: UUID | None = None
    product_name_at_sale: str = Field(..., min_length=1, max_length=255)
    unit_price_at_sale: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    quantity: int = Field(..., gt=0)
    line_total: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)

    @field_validator("product_name_at_sale", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def check_line_total(self) -> "SaleItemCreate":
        expected = self.unit_price_at_sale * self.quantity
        if abs(self.line_total - expected) > Decimal("0.01"):
            raise ValueError(
                f"line_total {self.line_total} != unit_price_at_sale x quantity = {expected}"
            )
        return self


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sale_id: UUID
    product_id: UUID | None
    product_name_at_sale: str
    unit_price_at_sale: Decimal
    quantity: int
    line_total: Decimal


class SaleCreate(BaseModel):
    id: UUID
    items: list[SaleItemCreate] = Field(..., min_length=1)
    total_amount: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    vat_amount: Decimal = Field(
        default=Decimal("0"), ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    payment_method: PaymentMethod
    cash_amount: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    mobile_money_amount: Decimal | None = Field(
        default=None, ge=Decimal("0"), max_digits=12, decimal_places=2
    )
    created_at: datetime

    @model_validator(mode="after")
    def validate_sale(self) -> "SaleCreate":
        items_total = sum(item.line_total for item in self.items)
        if abs(self.total_amount - items_total) > Decimal("0.01"):
            raise ValueError(
                f"total_amount {self.total_amount} != sum of line_totals {items_total}"
            )

        if self.vat_amount > self.total_amount:
            raise ValueError("vat_amount cannot exceed total_amount")

        if self.payment_method == PaymentMethod.mixed:
            if self.cash_amount is None or self.mobile_money_amount is None:
                raise ValueError(
                    "cash_amount and mobile_money_amount are required when payment_method is 'mixed'"
                )
            mixed_total = self.cash_amount + self.mobile_money_amount
            if abs(mixed_total - self.total_amount) > Decimal("0.01"):
                raise ValueError(
                    f"cash_amount + mobile_money_amount = {mixed_total} != total_amount {self.total_amount}"
                )

        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        now = datetime.now(UTC)
        if self.created_at > now + timedelta(seconds=_CLOCK_DRIFT_SECONDS):
            raise ValueError("created_at cannot be more than 5 minutes in the future")

        return self


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    receipt_number: int | None
    total_amount: Decimal
    vat_amount: Decimal
    payment_method: str
    cash_amount: Decimal | None
    mobile_money_amount: Decimal | None
    created_at: datetime
    synced_at: datetime
    items: list[SaleItemResponse]


SalesList = CursorPage[SaleResponse]


class PaymentMethodSummary(BaseModel):
    amount: Decimal
    count: int


class TopProduct(BaseModel):
    product_name: str
    quantity_sold: int
    revenue: Decimal


class DailySalesSummary(BaseModel):
    date: date
    total_amount: Decimal
    sales_count: int
    by_payment_method: dict[str, PaymentMethodSummary]
    top_products: list[TopProduct] = Field(default_factory=list, max_length=5)
