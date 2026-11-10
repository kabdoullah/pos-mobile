"""Modèles SQLAlchemy du module cash_register (ADR-0015).

ATTENTION :
- une session clôturée est FIGÉE et aucune session n'est supprimable : le
  trigger prevent_closed_cash_session_modification refuse l'UPDATE d'une ligne
  closed et tout DELETE ;
- cash_movements est IMMUABLE, comme sales.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SESSION_STATUSES = ("open", "closed")
MOVEMENT_TYPES = ("cash_in", "cash_out")
CASH_IN_REASONS = ("top_up", "float", "other")
CASH_OUT_REASONS = ("expense", "withdrawal", "supplies", "other")

# Renseignés à la clôture (obligatoires une fois closed).
_CLOSING_REQUIRED = (
    "expected_amount",
    "counted_amount",
    "discrepancy_amount",
    "closed_at",
    "closure_recorded_at",
)
# Nuls tant que la session est ouverte, facultatifs une fois closed.
_CLOSING_OPTIONAL = ("client_expected_amount", "closing_note", "closed_by")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


_OPEN_STATE = " AND ".join(f"{c} IS NULL" for c in _CLOSING_REQUIRED + _CLOSING_OPTIONAL)
_CLOSED_STATE = " AND ".join(f"{c} IS NOT NULL" for c in _CLOSING_REQUIRED)


class CashSession(Base):
    """Session de caisse d'un appareil (tiroir) : ouverture, puis clôture.

    L'id est un UUID v4 généré côté CLIENT (idempotence du sync). Une seule
    session ouverte par appareil : index unique partiel
    uq_cash_sessions_open_per_device (store_id, device_id) WHERE status = 'open',
    créé dans la migration.
    """

    __tablename__ = "cash_sessions"
    __table_args__ = (
        CheckConstraint(_in_list("status", SESSION_STATUSES), name="chk_cash_sessions_status"),
        CheckConstraint("opening_amount >= 0", name="chk_cash_sessions_opening_amount_positive"),
        CheckConstraint(
            "counted_amount IS NULL OR counted_amount >= 0",
            name="chk_cash_sessions_counted_amount_positive",
        ),
        CheckConstraint(
            f"(status = 'open' AND {_OPEN_STATE}) "
            f"OR (status = 'closed' AND {_CLOSED_STATE} "
            "AND discrepancy_amount = counted_amount - expected_amount)",
            name="chk_cash_sessions_state",
        ),
        CheckConstraint(
            "status <> 'closed' OR discrepancy_amount = 0 "
            "OR (closing_note IS NOT NULL AND length(trim(closing_note)) > 0)",
            name="chk_cash_sessions_note_on_discrepancy",
        ),
        CheckConstraint(
            "closed_at IS NULL OR closed_at >= opened_at",
            name="chk_cash_sessions_closed_after_opened",
        ),
    )

    # Pas de default : l'UUID DOIT être fourni par le client.
    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_cash_sessions_store"),
        nullable=False,
    )
    # Appareil (tiroir) qui porte la session.
    device_id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    opening_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    opening_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Horloge CLIENT.
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_cash_sessions_opened_by"),
        nullable=True,
    )
    # Recalculé par le serveur à la clôture.
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Ce que l'app avait affiché (traçabilité, jamais utilisé pour le calcul).
    client_expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    counted_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # counted_amount - expected_amount.
    discrepancy_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    closing_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Horloge CLIENT.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_cash_sessions_closed_by"),
        nullable=True,
    )
    # Horloge SERVEUR de l'enregistrement de la clôture.
    closure_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CashSession id={self.id} device_id={self.device_id} status={self.status}>"


class CashMovement(Base):
    """Entrée ou sortie d'espèces hors vente. IMMUABLE après création."""

    __tablename__ = "cash_movements"
    __table_args__ = (
        CheckConstraint(_in_list("type", MOVEMENT_TYPES), name="chk_cash_movements_type"),
        CheckConstraint(
            f"(type = 'cash_in' AND {_in_list('reason', CASH_IN_REASONS)}) "
            f"OR (type = 'cash_out' AND {_in_list('reason', CASH_OUT_REASONS)})",
            name="chk_cash_movements_reason",
        ),
        CheckConstraint("amount > 0", name="chk_cash_movements_amount_positive"),
        CheckConstraint(
            "reason <> 'other' OR (note IS NOT NULL AND length(trim(note)) > 0)",
            name="chk_cash_movements_other_requires_note",
        ),
    )

    # Pas de default : l'UUID DOIT être fourni par le client.
    id: Mapped[UUID] = mapped_column(SQLUUID(as_uuid=True), primary_key=True)
    store_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="RESTRICT", name="fk_cash_movements_store"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("cash_sessions.id", ondelete="RESTRICT", name="fk_cash_movements_session"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Horloge CLIENT.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_cash_movements_created_by"),
        nullable=True,
    )
    # Horloge serveur, sert au pull /sync/changes.
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<CashMovement id={self.id} session_id={self.session_id} "
            f"type={self.type} amount={self.amount}>"
        )
