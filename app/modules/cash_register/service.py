"""Logique métier du module cash_register (ADR-0015)."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.pagination import encode_cursor
from app.modules.cash_register.exceptions import (
    CashSessionAlreadyOpenError,
    CashSessionClosedError,
    IdempotencyConflictError,
    InsufficientCashError,
)
from app.modules.cash_register.models import CashMovement, CashSession
from app.modules.cash_register.repository import CashSessionRepository
from app.modules.cash_register.schemas import (
    CashMovementCreate,
    CashMovementResponse,
    CashSessionClose,
    CashSessionDetailResponse,
    CashSessionOpen,
    CashSessionPage,
    CashSessionResponse,
    CashSummary,
)
from app.modules.returns.service import ReturnService
from app.modules.sales.service import SaleService

# Index unique partiel (store_id, device_id) WHERE status = 'open'.
_OPEN_PER_DEVICE_INDEX = "uq_cash_sessions_open_per_device"


def _violated_constraint(exc: IntegrityError) -> str | None:
    """Nom de la contrainte violée, lu sur l'exception asyncpg d'origine."""
    driver_error = getattr(exc.orig, "__cause__", None)
    name = getattr(driver_error, "constraint_name", None)
    return name if isinstance(name, str) else None


class CashSessionService:
    """Service métier des sessions de caisse."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CashSessionRepository(db)
        self.sale_service = SaleService(db)
        self.return_service = ReturnService(db)

    async def compute_balance(self, session: CashSession) -> CashSummary:
        """Solde théorique de la session (spec §3).

        solde = ouverture + part espèces des ventes + entrées - sorties
                - remboursements en espèces.
        Session clôturée : `expected_amount` reste la valeur figée, et
        `late_impact` mesure ce qui est arrivé depuis (recalcul - figé).
        """
        sales = await self.sale_service.cash_totals_for_session(session.id)
        refunds = await self.return_service.cash_refund_total_for_session(session.id)
        cash_in, cash_out = await self.repo.movement_totals(session.id)
        current = session.opening_amount + sales.cash + cash_in - cash_out - refunds

        if session.status == "open":
            expected, late_impact, recalculated = current, Decimal("0"), False
        else:
            if session.expected_amount is None:
                # Exclu par chk_cash_sessions_state.
                raise RuntimeError(f"Closed cash session {session.id} has no expected_amount")
            expected = session.expected_amount
            late_impact = current - expected
            recalculated = expected != session.client_expected_amount

        return CashSummary(
            opening_amount=session.opening_amount,
            cash_sales=sales.cash,
            cash_sales_count=sales.cash_count,
            mobile_money_sales=sales.mobile_money,
            cash_in=cash_in,
            cash_out=cash_out,
            cash_refunds=refunds,
            expected_amount=expected,
            late_impact=late_impact,
            server_recalculated=recalculated,
        )

    async def open(
        self, store_id: UUID, user_id: UUID, payload: CashSessionOpen
    ) -> tuple[CashSession, bool]:
        """Ouvre une session ; (session, créée ?). Idempotent sur l'id client.

        Même id et même contenu : (existante, False). Même id, contenu
        différent : IdempotencyConflictError. Autre session déjà ouverte sur
        l'appareil : CashSessionAlreadyOpenError (index partiel, sûr face à
        deux requêtes concurrentes).
        """
        session = CashSession(
            id=payload.id,
            store_id=store_id,
            device_id=payload.device_id,
            status="open",
            opening_amount=payload.opening_amount,
            opening_note=payload.opening_note,
            opened_at=payload.opened_at,
            opened_by=user_id,
        )
        try:
            async with self.db.begin_nested():
                inserted = await self.repo.insert_session(session)
        except IntegrityError as exc:
            if _violated_constraint(exc) == _OPEN_PER_DEVICE_INDEX:
                raise CashSessionAlreadyOpenError(
                    "This device already has an open cash session.", field="device_id"
                ) from exc
            raise

        stored = await self.repo.get_by_id(payload.id)
        if stored is None:
            # Id déjà pris par une session invisible ici (autre boutique, RLS).
            raise IdempotencyConflictError("Cash session id already used.", field="id")
        if inserted:
            return stored, True
        if (
            stored.device_id != payload.device_id
            or stored.opening_amount != payload.opening_amount
            or stored.opened_at != payload.opened_at
        ):
            raise IdempotencyConflictError(
                "Cash session id already used with different content.", field="id"
            )
        return stored, False

    async def record_movement(
        self, store_id: UUID, user_id: UUID, session_id: UUID, payload: CashMovementCreate
    ) -> tuple[CashMovement, bool]:
        """Enregistre une entrée/sortie ; (mouvement, créé ?). Idempotent sur l'id client.

        Ordre (spec §3, §5.5) : retry du même id → existant ; session
        verrouillée (FOR UPDATE) ; clôturée et created_at > closed_at →
        CashSessionClosedError ; sortie sur session ouverte au-delà du solde →
        InsufficientCashError. Sur une session clôturée, un mouvement antérieur
        à la clôture est accepté sans contrôle de solde (l'argent a déjà bougé)
        et apparaît dans late_impact.
        """
        existing = await self.repo.get_movement(payload.id)
        if existing is not None:
            self._check_movement_replay(existing, session_id, payload)
            return existing, False

        session = await self.repo.get_for_update(session_id)
        if session is None:
            raise NotFoundError("Cash session not found.")
        if session.status == "closed":
            if session.closed_at is None:
                # Exclu par chk_cash_sessions_state.
                raise RuntimeError(f"Closed cash session {session.id} has no closed_at")
            if payload.created_at > session.closed_at:
                raise CashSessionClosedError(
                    "Cash session was closed before this movement.", field="created_at"
                )
        elif payload.type == "cash_out":
            balance = await self.compute_balance(session)
            if payload.amount > balance.expected_amount:
                raise InsufficientCashError(
                    "Cash out exceeds the session's expected cash balance.", field="amount"
                )

        movement = CashMovement(
            id=payload.id,
            store_id=store_id,
            session_id=session_id,
            type=payload.type,
            reason=payload.reason,
            amount=payload.amount,
            note=payload.note,
            created_at=payload.created_at,
            created_by=user_id,
        )
        inserted = await self.repo.insert_movement(movement)
        stored = await self.repo.get_movement(payload.id)
        if stored is None:
            # Id déjà pris par un mouvement invisible ici (autre boutique, RLS).
            raise IdempotencyConflictError("Cash movement id already used.", field="id")
        if not inserted:
            # Retry concurrent : l'autre requête a inséré entre-temps.
            self._check_movement_replay(stored, session_id, payload)
        return stored, inserted

    async def close(
        self, store_id: UUID, user_id: UUID, session_id: UUID, payload: CashSessionClose
    ) -> CashSessionDetailResponse:
        """Clôture la session (spec §5.6), dans la transaction de la requête.

        1. Session verrouillée (FOR UPDATE) : une vente concurrente (KEY SHARE
           via la FK) est soit commitée avant et comptée, soit après et visible
           dans late_impact.
        2. Déjà clôturée avec les mêmes counted_amount et closed_at : retry,
           détail existant. Valeurs différentes : CashSessionClosedError.
        3. expected_amount = solde recalculé en base sous le verrou ;
           client_expected_amount n'est jamais utilisé pour le calcul.
        4. Écart non nul sans note (vide ou blanche) : ValidationError.
        5. Un seul UPDATE : status, montants, note, closed_at, closed_by,
           closure_recorded_at = now().
        """
        session = await self.repo.get_for_update(session_id)
        if session is None or session.store_id != store_id:
            raise NotFoundError("Cash session not found.")

        if session.status == "closed":
            if (
                session.counted_amount == payload.counted_amount
                and session.closed_at == payload.closed_at
            ):
                return await self._detail(session)
            raise CashSessionClosedError(
                "Cash session is already closed with a different count or closing time."
            )

        if payload.closed_at < session.opened_at:
            raise ValidationError("closed_at cannot be before opened_at.", field="closed_at")

        expected = (await self.compute_balance(session)).expected_amount
        note = (
            payload.closing_note if payload.closing_note and payload.closing_note.strip() else None
        )
        if payload.counted_amount != expected and note is None:
            raise ValidationError(
                "closing_note is required when the count differs from the expected amount.",
                field="closing_note",
            )

        closed = await self.repo.close_session(
            session,
            expected_amount=expected,
            client_expected_amount=payload.client_expected_amount,
            counted_amount=payload.counted_amount,
            closing_note=note,
            closed_at=payload.closed_at,
            closed_by=user_id,
        )
        if not closed:
            # Exclu par le verrou FOR UPDATE : la session était ouverte.
            raise CashSessionClosedError("Cash session is already closed.")
        return await self._detail(session)

    @staticmethod
    def _check_movement_replay(
        stored: CashMovement, session_id: UUID, payload: CashMovementCreate
    ) -> None:
        if (
            stored.session_id != session_id
            or stored.type != payload.type
            or stored.amount != payload.amount
        ):
            raise IdempotencyConflictError(
                "Cash movement id already used with different content.", field="id"
            )

    async def get_active(self, device_id: UUID) -> CashSessionDetailResponse:
        """Session ouverte de l'appareil, avec résumé et mouvements ; 404 sinon."""
        session = await self.repo.get_open_for_device(device_id)
        if session is None:
            raise NotFoundError("No open cash session for this device.")
        return await self._detail(session)

    async def get_detail(self, session_id: UUID) -> CashSessionDetailResponse:
        """Session, résumé et mouvements ; 404 si inconnue ou d'une autre boutique."""
        session = await self.repo.get_by_id(session_id)
        if session is None:
            raise NotFoundError("Cash session not found.")
        return await self._detail(session)

    async def list_page(
        self, device_id: UUID | None, cursor: str | None, limit: int
    ) -> CashSessionPage:
        """Historique des sessions, du plus récent au plus ancien (opened_at)."""
        rows, has_more = await self.repo.list_page(device_id, cursor, limit)
        next_cursor: str | None = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = encode_cursor(
                {"id": str(last.id), "opened_at": last.opened_at.isoformat()}
            )
        return CashSessionPage(
            items=[CashSessionResponse.model_validate(row) for row in rows],
            next_cursor=next_cursor,
            has_more=has_more,
        )

    async def _detail(self, session: CashSession) -> CashSessionDetailResponse:
        summary = await self.compute_balance(session)
        movements = await self.repo.list_movements(session.id)
        return CashSessionDetailResponse(
            session=CashSessionResponse.model_validate(session),
            summary=summary,
            movements=[CashMovementResponse.model_validate(m) for m in movements],
        )
