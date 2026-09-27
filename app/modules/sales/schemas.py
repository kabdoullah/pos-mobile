"""Schémas Pydantic du module sales."""

from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated
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


class DiscountType(StrEnum):
    """Nature d'une réduction (ADR-0009)."""

    amount = "amount"
    percentage = "percentage"


# Montant FCFA positif, 2 décimales max (NUMERIC(12,2) en base).
Amount = Annotated[Decimal, Field(ge=Decimal("0"), max_digits=12, decimal_places=2)]
_TOLERANCE = Decimal("0.01")
_HUNDRED = Decimal(100)


def discount_amount_for(discount_type: DiscountType, value: Decimal, gross: Decimal) -> Decimal:
    """Montant d'une réduction sur un total brut — même règle que l'app (ADR-0009).

    Pourcentage arrondi au franc entier (demi vers le haut) ; jamais plus que
    le brut.
    """
    if discount_type == DiscountType.percentage:
        raw = (gross * value / _HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        raw = value
    return min(raw, gross)


def check_discount(
    discount_type: DiscountType | None,
    value: Decimal | None,
    amount: Decimal,
    gross: Decimal,
    label: str,
) -> None:
    """Vérifie qu'une réduction déclarée est cohérente avec son total brut.

    Lève ValueError (→ 422) : réduction sans type avec un montant, valeur non
    positive, pourcentage > 100, montant > brut, ou montant qui ne correspond
    pas au type et à la valeur.
    """
    if discount_type is None:
        if value is not None or amount != 0:
            raise ValueError(f"{label}: discount_amount requires discount_type")
        return
    if value is None or value <= 0:
        raise ValueError(f"{label}: discount_value must be positive")
    if discount_type == DiscountType.percentage and value > _HUNDRED:
        raise ValueError(f"{label}: percentage cannot exceed 100")
    if discount_type == DiscountType.amount and value > gross:
        raise ValueError(f"{label}: discount exceeds the amount it applies to")
    expected = discount_amount_for(discount_type, value, gross)
    if abs(amount - expected) > _TOLERANCE:
        raise ValueError(f"{label}: discount_amount {amount} != expected {expected}")


class SaleItemCreate(BaseModel):
    product_id: UUID | None = None
    product_name_at_sale: str = Field(..., min_length=1, max_length=255)
    unit_price_at_sale: Amount
    quantity: int = Field(..., gt=0)
    # Total net : unit_price_at_sale * quantity - discount_amount.
    line_total: Amount
    # Instantané ADR-0009 (absents des anciennes versions de l'app).
    purchase_price_at_sale: Amount | None = None
    discount_type: DiscountType | None = None
    discount_value: Amount | None = None
    discount_amount: Amount = Decimal("0")

    @field_validator("product_name_at_sale", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @model_validator(mode="after")
    def check_line_total(self) -> "SaleItemCreate":
        gross = self.unit_price_at_sale * self.quantity
        check_discount(self.discount_type, self.discount_value, self.discount_amount, gross, "item")
        expected = gross - self.discount_amount
        if abs(self.line_total - expected) > _TOLERANCE:
            raise ValueError(
                f"line_total {self.line_total} != unit_price_at_sale x quantity"
                f" - discount_amount = {expected}"
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
    purchase_price_at_sale: Decimal | None = None
    discount_type: str | None = None
    discount_value: Decimal | None = None
    discount_amount: Decimal = Decimal("0")


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
    # Remise globale (ADR-0009), appliquée au sous-total des lignes.
    discount_type: DiscountType | None = None
    discount_value: Amount | None = None
    discount_amount: Amount = Decimal("0")

    @model_validator(mode="after")
    def validate_sale(self) -> "SaleCreate":
        subtotal = sum((item.line_total for item in self.items), Decimal("0"))
        check_discount(
            self.discount_type, self.discount_value, self.discount_amount, subtotal, "sale"
        )
        expected_total = subtotal - self.discount_amount
        if abs(self.total_amount - expected_total) > _TOLERANCE:
            raise ValueError(
                f"total_amount {self.total_amount} != sum of line_totals"
                f" - discount_amount = {expected_total}"
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
    discount_type: str | None = None
    discount_value: Decimal | None = None
    discount_amount: Decimal = Decimal("0")
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
