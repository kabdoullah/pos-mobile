"""Exceptions métier du module cash_register (ADR-0015, spec §5)."""

from app.core.exceptions import ConflictError, ValidationError


class CashSessionAlreadyOpenError(ConflictError):
    """L'appareil a déjà une autre session ouverte (index uq_cash_sessions_open_per_device)."""

    code = "CASH_SESSION_ALREADY_OPEN"


class CashSessionClosedError(ConflictError):
    """Session clôturée : mouvement postérieur à la clôture, ou clôture différente."""

    code = "CASH_SESSION_CLOSED"


class InsufficientCashError(ValidationError):
    """Sortie d'espèces supérieure au solde théorique de la session."""

    code = "INSUFFICIENT_CASH"


class IdempotencyConflictError(ConflictError):
    """Même UUID client qu'une ligne existante, avec un contenu différent."""

    code = "IDEMPOTENCY_CONFLICT"
