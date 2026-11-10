"""Logique métier du module cash_register (ADR-0015)."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.cash_register.models import CashSession
from app.modules.cash_register.repository import CashSessionRepository
from app.modules.cash_register.schemas import CashSummary
from app.modules.returns.service import ReturnService
from app.modules.sales.service import SaleService


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
