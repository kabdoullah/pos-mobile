"""Routes du module auth."""

from fastapi import APIRouter, status

from app.core.db import DbSession
from app.modules.auth import schemas
from app.modules.auth.service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def register(payload: schemas.RegisterRequest, db: DbSession) -> schemas.RegisterResponse:
    """Crée un compte utilisateur avec numéro de téléphone + mot de passe. Email optionnel."""
    service = AuthService(db)
    user = await service.register(payload)
    message = (
        "Account created. Check your email to verify your address."
        if user.email is not None
        else "Account created."
    )
    return schemas.RegisterResponse(
        user_id=user.id,
        phone_number=user.phone_number,
        message=message,
    )


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Obtenir un JWT",
)
async def login(payload: schemas.LoginRequest, db: DbSession) -> schemas.TokenResponse:
    """Authentifie l'utilisateur via numéro de téléphone + mot de passe."""
    service = AuthService(db)
    return await service.login(payload)


@router.post(
    "/refresh",
    response_model=schemas.TokenResponse,
    summary="Renouveler un JWT",
)
async def refresh(payload: schemas.RefreshRequest, db: DbSession) -> schemas.TokenResponse:
    """Renouvelle l'access token à partir d'un refresh token valide."""
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Demander un email de reset",
)
async def forgot_password(payload: schemas.ForgotPasswordRequest, db: DbSession) -> None:
    """Envoie un email de réinitialisation. Renvoie 204 même si l'email n'existe pas."""
    service = AuthService(db)
    await service.send_password_reset(payload.email)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer la réinitialisation",
)
async def reset_password(payload: schemas.ResetPasswordRequest, db: DbSession) -> None:
    """Réinitialise le mot de passe via le token reçu par email."""
    service = AuthService(db)
    await service.reset_password(payload.token, payload.new_password)
