"""Schémas Pydantic du module cash_register (ADR-0015)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.core.pagination import CursorPage
from app.modules.cash_register.models import CASH_IN_REASONS, CASH_OUT_REASONS

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


_REASONS_BY_TYPE = {"cash_in": CASH_IN_REASONS, "cash_out": CASH_OUT_REASONS}


class CashMovementCreate(BaseModel):
    """Entrée ou sortie d'espèces (spec §5.5). L'id est généré par l'app.

    Les CHECK de cash_movements imposent déjà ces règles ; les valider ici
    donne une 422 VALIDATION_ERROR plutôt qu'une erreur base.
    """

    id: UUID
    type: Literal["cash_in", "cash_out"]
    reason: str
    amount: Decimal = Field(..., gt=Decimal("0"), max_digits=12, decimal_places=2)
    # validate_default : la note absente doit aussi être contrôlée (reason = other).
    note: str | None = Field(default=None, max_length=500, validate_default=True)
    created_at: datetime

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str, info: ValidationInfo) -> str:
        movement_type = info.data.get("type")
        if movement_type is not None and v not in _REASONS_BY_TYPE[movement_type]:
            allowed = ", ".join(_REASONS_BY_TYPE[movement_type])
            raise ValueError(f"reason must be one of {allowed} for {movement_type}")
        return v

    @field_validator("note")
    @classmethod
    def check_note(cls, v: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("reason") == "other" and (v is None or not v.strip()):
            raise ValueError("note is required when reason is 'other'")
        return v

    @field_validator("created_at")
    @classmethod
    def check_created_at(cls, v: datetime) -> datetime:
        return check_client_timestamp(v, "created_at")


class CashSessionClose(BaseModel):
    """Clôture d'une session (spec §5.6).

    `client_expected_amount` est ce que l'app affichait : conservé pour la
    traçabilité, jamais utilisé pour le calcul (le serveur recalcule).
    """

    counted_amount: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    # Pas de ge=0 : les remboursements en espèces ne sont jamais bloqués, le solde
    # peut être négatif et la clôture doit rester possible.
    client_expected_amount: Decimal = Field(..., max_digits=12, decimal_places=2)
    closing_note: str | None = Field(default=None, max_length=500)
    closed_at: datetime

    @field_validator("closed_at")
    @classmethod
    def check_closed_at(cls, v: datetime) -> datetime:
        return check_client_timestamp(v, "closed_at")


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
