"""Exceptions métier et handlers FastAPI."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Exception de base pour les erreurs métier."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "APP_ERROR"

    def __init__(self, message: str, field: str | None = None) -> None:
        self.message = message
        self.field = field
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


class ConflictError(AppError):
    """Conflit lors d'un upsert ou d'un sync (état serveur plus récent)."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class ValidationError(AppError):
    """Validation métier échouée (différent de la validation Pydantic)."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre les handlers d'exception sur l'app FastAPI."""

    @app.exception_handler(AppError)
    async def handle_app_exception(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                "field": exc.field,
            },
        )
