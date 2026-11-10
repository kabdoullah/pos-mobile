"""Schémas Pydantic du module cash_register (ADR-0015)."""

from decimal import Decimal

from pydantic import BaseModel


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
