"""Accès aux données du module cash_register (ADR-0015).

Toutes les requêtes passent par la session tenant : la RLS restreint les
lignes à la boutique courante.
"""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_register.models import CashMovement, CashSession


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
        """Session verrouillée (SELECT … FOR UPDATE) jusqu'à la fin de la transaction."""
        stmt = select(CashSession).where(CashSession.id == session_id).with_for_update()
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_open_for_device(self, device_id: UUID) -> CashSession | None:
        """Session ouverte de l'appareil (au plus une, index unique partiel)."""
        stmt = select(CashSession).where(
            CashSession.device_id == device_id, CashSession.status == "open"
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

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
