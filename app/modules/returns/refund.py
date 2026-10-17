"""Calcul du montant remboursable d'un retour (ADR-0010).

Fonctions pures, reproduites à l'identique par l'app mobile : le client calcule
le montant affiché, le serveur le recalcule et refuse tout écart.

Règle :
1. Le montant payé d'une ligne est sa part du total encaissé de la vente :
   la remise globale est répartie au prorata des line_total, au franc entier,
   par la méthode du plus fort reste (égalités départagées par l'id de ligne,
   ordre croissant). La somme des montants payés vaut exactement le total
   encaissé (arrondi au franc inférieur).
2. Rembourser q unités d'une ligne de Q unités dont r sont déjà retournées :
   floor(payé x (r+q) / Q) - floor(payé x r / Q). Formule cumulative : la somme
   des retours d'une ligne vaut exactement son montant payé quand elle est
   entièrement retournée, jamais davantage.

Les calculs sont faits en entiers (centimes puis francs) : aucune division
décimale inexacte.
"""

from decimal import Decimal
from uuid import UUID


def _cents(amount: Decimal) -> int:
    return int(amount * 100)


def allocate_paid_amounts(lines: list[tuple[UUID, Decimal]], total: Decimal) -> dict[UUID, int]:
    """Montant payé (francs entiers) de chaque ligne `(sale_item_id, line_total)`."""
    total_francs = int(total)
    subtotal_cents = sum(_cents(line_total) for _, line_total in lines)
    if subtotal_cents == 0:
        return {item_id: 0 for item_id, _ in lines}

    quotas: list[tuple[UUID, int, int]] = []
    for item_id, line_total in lines:
        numerator = _cents(line_total) * total_francs
        quotas.append((item_id, numerator // subtotal_cents, numerator % subtotal_cents))

    paid = {item_id: floor for item_id, floor, _ in quotas}
    leftover = total_francs - sum(paid.values())
    by_remainder = sorted(quotas, key=lambda q: (-q[2], str(q[0])))
    for item_id, _, _ in by_remainder[:leftover]:
        paid[item_id] += 1
    return paid


def refund_for(paid: int, sold: int, already_returned: int, quantity: int) -> int:
    """Montant (francs entiers) à rembourser pour `quantity` unités d'une ligne."""
    returned_after = already_returned + quantity
    return paid * returned_after // sold - paid * already_returned // sold
