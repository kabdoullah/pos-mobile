"""Accès aux données du module cash_register (ADR-0015).

Toutes les requêtes passent par la session tenant : la RLS restreint les
lignes à la boutique courante.
"""

from datetime import datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import decode_cursor
from app.modules.cash_register.models import CashMovement, CashSession


class _CursorData(TypedDict):
    id: UUID
    opened_at: datetime


def _parse_cursor(cursor: str) -> _CursorData | None:
    """Décode et valide un cursor opaque. Retourne None si invalide."""
    raw = decode_cursor(cursor)
    if raw is None:
        return None
    try:
        return _CursorData(
            id=UUID(str(raw["id"])),
            opened_at=datetime.fromisoformat(str(raw["opened_at"])),
        )
    except (KeyError, ValueError):
        return None


def _columns(row: CashSession | CashMovement) -> dict[str, object]:
    """Valeurs des colonnes posées sur l'instance (les défauts serveur restent absents)."""
    return {
        column.key: getattr(row, column.key)
        for column in row.__table__.columns
        if getattr(row, column.key) is not None
    }


class CashSessionRepository:
    """Repository des sessions de caisse et de leurs mouvements."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, session_id: UUID) -> CashSession | None:
        return await self.db.get(CashSession, session_id)

    async def get_for_update(self, session_id: UUID) -> CashSession | None:
        """Session verrouillée (SELECT … FOR UPDATE) jusqu'à la fin de la transaction.

        populate_existing : un objet déjà présent dans l'identity map est
        rafraîchi avec les valeurs lues sous le verrou (sinon une clôture
        commitée entre-temps resterait invisible).
        """
        stmt = (
            select(CashSession)
            .where(CashSession.id == session_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def close_session(
        self,
        session: CashSession,
        *,
        expected_amount: Decimal,
        client_expected_amount: Decimal,
        counted_amount: Decimal,
        closing_note: str | None,
        closed_at: datetime,
        closed_by: UUID,
    ) -> bool:
        """Écrit la clôture en un seul UPDATE et rafraîchit `session` ; False si déjà close.

        La session doit être ouverte et verrouillée (get_for_update) : l'écart
        est dérivé ici de counted - expected, comme l'exige
        chk_cash_sessions_state ; closure_recorded_at prend l'horloge serveur.
        """
        stmt = (
            update(CashSession)
            .where(CashSession.id == session.id, CashSession.status == "open")
            .values(
                status="closed",
                expected_amount=expected_amount,
                client_expected_amount=client_expected_amount,
                counted_amount=counted_amount,
                discrepancy_amount=counted_amount - expected_amount,
                closing_note=closing_note,
                closed_at=closed_at,
                closed_by=closed_by,
                closure_recorded_at=func.now(),
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.db.execute(stmt)
        if result.rowcount != 1:  # type: ignore[attr-defined]
            return False
        await self.db.refresh(session)
        return True

    async def get_open_for_device(self, device_id: UUID) -> CashSession | None:
        """Session ouverte de l'appareil (au plus une, index unique partiel)."""
        stmt = select(CashSession).where(
            CashSession.device_id == device_id, CashSession.status == "open"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_page(
        self, device_id: UUID | None, cursor: str | None, limit: int
    ) -> tuple[list[CashSession], bool]:
        """Historique paginé, tri (opened_at DESC, id DESC). Retourne (items, has_more)."""
        stmt = select(CashSession)
        if device_id is not None:
            stmt = stmt.where(CashSession.device_id == device_id)
        if cursor:
            parsed = _parse_cursor(cursor)
            if parsed is not None:
                stmt = stmt.where(
                    tuple_(CashSession.opened_at, CashSession.id)
                    < (parsed["opened_at"], parsed["id"])
                )
        stmt = stmt.order_by(CashSession.opened_at.desc(), CashSession.id.desc()).limit(limit + 1)
        rows = list((await self.db.execute(stmt)).scalars().all())
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def insert_session(self, session: CashSession) -> bool:
        """Insère la session ; False si l'id existe déjà (retry idempotent).

        ON CONFLICT ne vise que l'id : une seconde session ouverte pour le même
        appareil viole l'index partiel uq_cash_sessions_open_per_device et lève
        IntegrityError.
        """
        stmt = (
            pg_insert(CashSession)
            .values(**_columns(session))
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(CashSession.id)
        )
        inserted = (await self.db.execute(stmt)).scalar_one_or_none()
        return inserted is not None

    async def movement_totals(self, session_id: UUID) -> tuple[Decimal, Decimal]:
        """(Σ entrées, Σ sorties) des mouvements de la session."""
        zero = Decimal("0")

        def total(movement_type: str) -> ColumnElement[Decimal]:
            amount = case((CashMovement.type == movement_type, CashMovement.amount), else_=zero)
            return func.coalesce(func.sum(amount), zero)

        stmt = select(total("cash_in"), total("cash_out")).where(
            CashMovement.session_id == session_id
        )
        cash_in, cash_out = (await self.db.execute(stmt)).one()
        return cash_in, cash_out

    async def list_movements(self, session_id: UUID) -> list[CashMovement]:
        """Mouvements de la session, du plus récent au plus ancien."""
        stmt = (
            select(CashMovement)
            .where(CashMovement.session_id == session_id)
            .order_by(CashMovement.created_at.desc(), CashMovement.id.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_movement(self, movement_id: UUID) -> CashMovement | None:
        return await self.db.get(CashMovement, movement_id)

    async def insert_movement(self, movement: CashMovement) -> bool:
        """Insère le mouvement ; False si l'id existe déjà (retry idempotent)."""
        stmt = (
            pg_insert(CashMovement)
            .values(**_columns(movement))
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(CashMovement.id)
        )
        inserted = (await self.db.execute(stmt)).scalar_one_or_none()
        return inserted is not None
