"""Schémas Pydantic du module cash_register (ADR-0015)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationInfo,
    field_validator,
    model_validator,
)

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


# Coupures FCFA acceptées par la billetterie (ADR-0016), gamme BCEAO. Même
# liste que `fcfaDenominations` côté Flutter : ajouter une coupure ici AVANT de
# publier une version de l'app qui la propose.
DENOMINATIONS: dict[str, tuple[int, ...]] = {
    "bill": (10000, 5000, 2000, 1000, 500),
    "coin": (500, 250, 200, 100, 50, 25, 10, 5),
}
# Plafond par coupure : au-delà, c'est une erreur de saisie, pas un comptage.
_MAX_QUANTITY = 100_000
_MAX_COUNT_LINES = sum(len(values) for values in DENOMINATIONS.values())


class CashCountLineIn(BaseModel):
    """Quantité comptée d'une coupure. Le sous-total est recalculé par le serveur.

    StrictInt : une quantité ou une coupure décimale (2.5, "3") est refusée.
    """

    denomination_type: Literal["bill", "coin"]
    denomination: StrictInt
    quantity: StrictInt = Field(..., ge=0, le=_MAX_QUANTITY)

    @model_validator(mode="after")
    def check_denomination(self) -> "CashCountLineIn":
        if self.denomination not in DENOMINATIONS[self.denomination_type]:
            raise ValueError(f"unknown {self.denomination_type} denomination: {self.denomination}")
        return self

    @property
    def subtotal(self) -> Decimal:
        return Decimal(self.denomination) * self.quantity


def count_key(lines: list[CashCountLineIn] | None) -> frozenset[tuple[str, Decimal, int]]:
    """Contenu d'un comptage, comparable à celui des lignes stockées (retry)."""
    return frozenset(
        (line.denomination_type, Decimal(line.denomination), line.quantity) for line in lines or []
    )


def check_count(
    lines: list[CashCountLineIn] | None, amount: Decimal | None, field: str
) -> list[CashCountLineIn] | None:
    """Une ligne par coupure, et Σ sous-totaux = montant de la session.

    Le serveur recalcule le total au lieu de faire confiance à l'app ; le
    montant reste envoyé pour la compatibilité des anciennes versions (sans
    comptage) et l'idempotence.
    """
    if lines is None:
        return None
    keys = [(line.denomination_type, line.denomination) for line in lines]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{field} has duplicate denominations")
    total = sum((line.subtotal for line in lines), Decimal("0"))
    if amount is not None and total != amount:
        raise ValueError(f"{field} total ({total}) does not match the amount ({amount})")
    return lines


class CashSessionOpen(BaseModel):
    """Ouverture d'une session (spec §5.1). L'id est généré par l'app.

    `opening_count` (billetterie, ADR-0016) est facultatif : absent en mode
    « Total seulement » et pour les anciennes versions de l'app.
    """

    id: UUID
    device_id: UUID
    opening_amount: Decimal = Field(..., ge=Decimal("0"), max_digits=12, decimal_places=2)
    opening_note: str | None = Field(default=None, max_length=500)
    opened_at: datetime
    opening_count: list[CashCountLineIn] | None = Field(
        default=None, min_length=1, max_length=_MAX_COUNT_LINES
    )

    @field_validator("opened_at")
    @classmethod
    def check_opened_at(cls, v: datetime) -> datetime:
        return check_client_timestamp(v, "opened_at")

    @field_validator("opening_count")
    @classmethod
    def check_opening_count(
        cls, v: list[CashCountLineIn] | None, info: ValidationInfo
    ) -> list[CashCountLineIn] | None:
        return check_count(v, info.data.get("opening_amount"), "opening_count")


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
    # Billetterie de clôture (ADR-0016), facultative comme opening_count.
    closing_count: list[CashCountLineIn] | None = Field(
        default=None, min_length=1, max_length=_MAX_COUNT_LINES
    )

    @field_validator("closing_count")
    @classmethod
    def check_closing_count(
        cls, v: list[CashCountLineIn] | None, info: ValidationInfo
    ) -> list[CashCountLineIn] | None:
        return check_count(v, info.data.get("counted_amount"), "closing_count")

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


class CashCountLineResponse(BaseModel):
    """Ligne de billetterie enregistrée."""

    model_config = ConfigDict(from_attributes=True)

    denomination_type: str
    denomination: Decimal
    quantity: int
    subtotal: Decimal


class CashCountResponse(BaseModel):
    """Comptage d'une opération (ouverture ou clôture), billets puis pièces,
    de la plus grande coupure à la plus petite."""

    lines: list[CashCountLineResponse]
    bills_total: Decimal
    coins_total: Decimal
    total: Decimal


class CashSessionDetailResponse(BaseModel):
    """Session, résumé, mouvements (du plus récent au plus ancien) et
    comptages (null sans billetterie)."""

    session: CashSessionResponse
    summary: CashSummary
    movements: list[CashMovementResponse]
    opening_count: CashCountResponse | None = None
    closing_count: CashCountResponse | None = None


CashSessionPage = CursorPage[CashSessionResponse]
