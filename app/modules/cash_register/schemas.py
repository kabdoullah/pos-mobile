"""Schémas Pydantic du module cash_register (ADR-0015)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.pagination import CursorPage

# Même tolérance d'horloge client que SaleCreate.
_CLOCK_DRIFT_SECONDS = 300


def check_client_timestamp(value: datetime, field: str) -> datetime:
    """Horodatage client : fuseau obligatoire, au plus 5 min dans le futur."""
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    if value > datetime.now(UTC) + timedelta(seconds=_CLOCK_DRIFT_SECONDS):
        raise ValueError(f"{field} cannot be more than 5 minutes in the future")
    return value


class CashSessionOpen(BaseModel):
    """Ouverture d'une session (spec §5.1). L'id est généré par l'app."""

    id: UUID
    device_id: UUID
    opening_amount: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    opening_note: str | None = Field(default=None, max_length=500)
    opened_at: datetime

    @field_validator("opened_at")
    @classmethod
    def check_opened_at(cls, v: datetime) -> datetime:
        return check_client_timestamp(v, "opened_at")


class CashSessionResponse(BaseModel):
    """Session de caisse (spec §5.8). Montants sérialisés en chaînes."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    device_id: UUID
    status: str
    opening_amount: Decimal
    opening_note: str | None
    opened_at: datetime
    opened_by: UUID | None
    expected_amount: Decimal | None
    client_expected_amount: Decimal | None
    counted_amount: Decimal | None
    discrepancy_amount: Decimal | None
    closing_note: str | None
    closed_at: datetime | None
    closed_by: UUID | None


class CashMovementResponse(BaseModel):
    """Entrée ou sortie d'espèces d'une session."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    type: str
    reason: str
    amount: Decimal
    note: str | None
    created_at: datetime
    created_by: UUID | None
    synced_at: datetime


class CashSummary(BaseModel):
    """Résumé d'une session : composantes du solde théorique (spec §3, §5.8).

    Session ouverte : `expected_amount` est le solde courant. Session
    clôturée : c'est le montant figé, et `late_impact` = recalcul - figé.
    `mobile_money_sales` est informatif et n'entre jamais dans le solde.
    """

    opening_amount: Decimal
    cash_sales: Decimal
    cash_sales_count: int
    mobile_money_sales: Decimal
    cash_in: Decimal
    cash_out: Decimal
    cash_refunds: Decimal
    expected_amount: Decimal
    late_impact: Decimal
    server_recalculated: bool


class CashSessionDetailResponse(BaseModel):
    """Session, résumé et mouvements (du plus récent au plus ancien)."""

    session: CashSessionResponse
    summary: CashSummary
    movements: list[CashMovementResponse]


CashSessionPage = CursorPage[CashSessionResponse]
