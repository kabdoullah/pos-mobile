"""Exceptions métier et handlers FastAPI."""

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Exception de base pour les erreurs métier."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        self.message = message
        self.field = field
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    """Ressource non trouvée."""

    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class UnauthorizedError(AppError):
    """JWT manquant, invalide, ou expiré."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    """L'utilisateur n'a pas les droits d'accéder à cette ressource."""

    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class StoreSuspendedError(ForbiddenError):
    """La boutique est suspendue par la plateforme."""

    code = "STORE_SUSPENDED"

    def __init__(self) -> None:
        super().__init__(
            "Store is suspended.",
            details={
                "support_contact": settings.support_contact,
                "support_whatsapp": settings.support_whatsapp,
            },
        )


class ConflictError(AppError):
    """Conflit lors d'un upsert ou d'un sync (état serveur plus récent)."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class ValidationError(AppError):
    """Validation métier échouée (différent de la validation Pydantic)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


class PayloadTooLargeError(AppError):
    """Fichier envoyé trop volumineux (ex. image > 5 Mo)."""

    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "PAYLOAD_TOO_LARGE"


# Préfixes de `loc` ajoutés par FastAPI pour situer le champ dans la requête.
_REQUEST_LOCATIONS = {"body", "query", "path", "header", "cookie"}
_VALUE_ERROR_PREFIX = "Value error, "


def _validation_error_response(errors: Sequence[Any]) -> JSONResponse:
    """Aplatit des erreurs Pydantic/FastAPI au format `{detail, code, field}`.

    Seule la première erreur est renvoyée (le client affiche un message). Les
    valeurs saisies (`input`) ne sont jamais loguées : elles peuvent contenir
    un mot de passe ou un PIN.
    """
    first = errors[0] if errors else {}
    detail = str(first.get("msg", "Validation error")).removeprefix(_VALUE_ERROR_PREFIX)
    loc = [part for part in first.get("loc", ()) if part not in _REQUEST_LOCATIONS]
    field = next((str(part) for part in loc if isinstance(part, str)), None)
    logger.info(
        "validation_error",
        extra={"errors": [{"loc": e.get("loc"), "type": e.get("type")} for e in errors]},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail, "code": "VALIDATION_ERROR", "field": field},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre les handlers d'exception sur l'app FastAPI."""

    @app.exception_handler(AppError)
    async def handle_app_exception(_request: Request, exc: AppError) -> JSONResponse:
        content: dict[str, object] = {
            "detail": exc.message,
            "code": exc.code,
            "field": exc.field,
        }
        if exc.details is not None:
            content["details"] = exc.details
        return JSONResponse(status_code=exc.status_code, content=content)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(PydanticValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError | PydanticValidationError
    ) -> JSONResponse:
        return _validation_error_response(exc.errors())
