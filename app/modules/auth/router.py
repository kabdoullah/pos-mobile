"""Routes du module auth."""

from fastapi import APIRouter, status

from app.core.db import DbSession, TenantDbSession
from app.core.dependencies import CurrentUserId
from app.modules.auth import schemas
from app.modules.auth.service import AuthService, UserService

router = APIRouter()
users_router = APIRouter()


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


# ---------------------------------------------------------------------------
# Profil (/api/v1/users/me) — ADR-0008
# ---------------------------------------------------------------------------


@users_router.get("/me", response_model=schemas.UserMeResponse, summary="Mon profil")
async def get_me(db: TenantDbSession, user_id: CurrentUserId) -> schemas.UserMeResponse:
    """Profil de l'utilisateur connecté."""
    user = await UserService(db).get_me(user_id)
    return schemas.UserMeResponse.model_validate(user)


@users_router.patch(
    "/me", response_model=schemas.UserMeResponse, summary="Mettre à jour mon profil"
)
async def update_me(
    payload: schemas.UserMeUpdate, db: TenantDbSession, user_id: CurrentUserId
) -> schemas.UserMeResponse:
    """Met à jour le nom affiché « Vendeur : … » sur les reçus (vide = retiré)."""
    user = await UserService(db).update_me(user_id, payload)
    return schemas.UserMeResponse.model_validate(user)
