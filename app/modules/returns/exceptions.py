"""Exceptions métier du module returns."""

from enum import StrEnum


class ReturnRejectionCode(StrEnum):
    """Motif d'un refus définitif : renvoyer le même retour ne réussira jamais."""

    sale_not_found = "sale_not_found"
    item_not_in_sale = "item_not_in_sale"
    quantity_exceeded = "quantity_exceeded"
    amount_mismatch = "amount_mismatch"


class ReturnRejectedError(Exception):
    """Retour refusé par les règles métier (quantités, montants, vente inconnue)."""

    def __init__(self, code: ReturnRejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
