"""Routes du module auth."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core.db import DbSession, TenantDbSession
from app.core.dependencies import CurrentUserId
from app.core.email import EmailService, get_email_service
from app.core.exceptions import StoreSuspendedError
from app.core.rate_limit import client_ip, rate_limiter
from app.modules.auth import schemas
from app.modules.auth.service import AuthService, UserService, normalize_login_phone

router = APIRouter()
users_router = APIRouter()

_MINUTE = 60
_HOUR = 3600

# Limites strictes par compte visé, plus larges par IP : les opérateurs mobiles
# partagent souvent une IP entre de nombreux abonnés (CGNAT).
#
# Login : chaque tentative est comptée, et un succès remet les compteurs à
# zéro (seuls les échecs restent donc comptés).
# La limite stricte porte sur (numéro, IP). La limite par numéro seul freine
# le brute force distribué. Les deux partagent la même fenêtre : une IP
# apporte au plus _LOGIN_FAILS_PER_PHONE_IP échecs au compteur du numéro, donc
# bloquer un compte demande au moins 50 / 5 = 10 IP distinctes.
_LOGIN_WINDOW = 15 * 60
_LOGIN_FAILS_PER_PHONE_IP = 5  # par 15 minutes
_LOGIN_FAILS_PER_PHONE = 50  # par 15 minutes
_LOGIN_PER_IP = 30  # par minute, toutes tentatives
_FORGOT_PER_EMAIL = 3  # par heure
_FORGOT_PER_IP = 10  # par heure
_REGISTER_PER_IP = 10  # par heure
_RESET_PER_IP = 10  # par heure
_VERIFY_PER_IP = 10  # par heure
_RESEND_VERIFICATION_PER_USER = 3  # par heure


def get_auth_service(
    db: DbSession, email_service: Annotated[EmailService, Depends(get_email_service)]
) -> AuthService:
    """Construit l'AuthService de la requête avec ses dépendances injectées."""
    return AuthService(db, email_service)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def register(
    payload: schemas.RegisterRequest, service: AuthServiceDep, request: Request
) -> schemas.RegisterResponse:
    """Crée un compte utilisateur avec numéro de téléphone, mot de passe et email."""
    await rate_limiter.hit(f"register:ip:{client_ip(request)}", _REGISTER_PER_IP, _HOUR)
    user = await service.register(payload)
    return schemas.RegisterResponse(
        user_id=user.id,
        phone_number=user.phone_number,
        message="Account created. Check your email to verify your address.",
    )


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Obtenir un JWT",
)
async def login(
    payload: schemas.LoginRequest, service: AuthServiceDep, request: Request
) -> schemas.TokenResponse:
    """Authentifie l'utilisateur via numéro de téléphone + mot de passe."""
    ip = client_ip(request)
    # Même normalisation que la recherche en base : une clé ⇔ un compte visé.
    phone = normalize_login_phone(payload.phone_number)
    await rate_limiter.hit(f"login:ip:{ip}", _LOGIN_PER_IP, _MINUTE)
    # Familles de clés aux préfixes distincts ; l'IP (sans « | ») précède le
    # numéro saisi librement, pour qu'aucune saisie ne fabrique la clé d'un autre.
    attempt_keys = (
        (f"login:attempt:phone_ip:{ip}|{phone}", _LOGIN_FAILS_PER_PHONE_IP, _LOGIN_WINDOW),
        (f"login:attempt:phone:{phone}", _LOGIN_FAILS_PER_PHONE, _LOGIN_WINDOW),
    )
    # La tentative est comptée AVANT la vérification (atomiquement) : des
    # requêtes concurrentes ne peuvent pas toutes passer avant le 1er échec.
    await rate_limiter.hit_many(attempt_keys)
    try:
        tokens = await service.login(payload)
    except StoreSuspendedError:
        # Levée seulement après vérification du mot de passe : identifiants
        # justes, ce n'est pas un échec. Toute autre erreur (identifiants
        # refusés, panne) laisse la tentative comptée.
        await _clear_login_attempts(attempt_keys)
        raise
    await _clear_login_attempts(attempt_keys)
    return tokens


async def _clear_login_attempts(keys: tuple[tuple[str, int, int], ...]) -> None:
    for key, _, _ in keys:
        await rate_limiter.clear(key)


@router.post(
    "/refresh",
    response_model=schemas.TokenResponse,
    summary="Renouveler un JWT",
)
async def refresh(
    payload: schemas.RefreshRequest, service: AuthServiceDep
) -> schemas.TokenResponse:
    """Renouvelle l'access token à partir d'un refresh token valide."""
    return await service.refresh(payload.refresh_token)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Demander un email de reset",
)
async def forgot_password(
    payload: schemas.ForgotPasswordRequest, service: AuthServiceDep, request: Request
) -> None:
    """Envoie un email de réinitialisation. Renvoie 204 même si l'email n'existe pas."""
    await rate_limiter.hit(f"forgot:ip:{client_ip(request)}", _FORGOT_PER_IP, _HOUR)
    await rate_limiter.hit(f"forgot:email:{payload.email.lower()}", _FORGOT_PER_EMAIL, _HOUR)
    await service.send_password_reset(payload.email)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer la réinitialisation",
)
async def reset_password(
    payload: schemas.ResetPasswordRequest, service: AuthServiceDep, request: Request
) -> None:
    """Réinitialise le mot de passe via le token reçu par email."""
    await rate_limiter.hit(f"reset:ip:{client_ip(request)}", _RESET_PER_IP, _HOUR)
    await service.reset_password(payload.token, payload.new_password)


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer l'adresse email",
)
async def verify_email(
    payload: schemas.VerifyEmailRequest, service: AuthServiceDep, request: Request
) -> None:
    """Confirme l'adresse email via le token reçu par email (appelé par la page /auth/verify-email)."""
    await rate_limiter.hit(f"verify:ip:{client_ip(request)}", _VERIFY_PER_IP, _HOUR)
    await service.verify_email(payload.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Renvoyer l'email de vérification",
)
async def resend_verification(
    db: TenantDbSession,
    user_id: CurrentUserId,
    email_service: Annotated[EmailService, Depends(get_email_service)],
) -> None:
    """Renvoie le lien de vérification à l'utilisateur connecté. 204 si déjà vérifié."""
    await rate_limiter.hit(
        f"resend_verification:user:{user_id}", _RESEND_VERIFICATION_PER_USER, _HOUR
    )
    await AuthService(db, email_service).resend_verification(user_id)


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


@users_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer mon compte")
async def delete_me(
    payload: schemas.DeleteAccountRequest, db: TenantDbSession, user_id: CurrentUserId
) -> None:
    """Supprime définitivement le compte, la boutique et toutes ses données (ADR-0011).

    Mot de passe revérifié : 403 s'il est faux.
    """
    await UserService(db).delete_me(user_id, payload.password)
