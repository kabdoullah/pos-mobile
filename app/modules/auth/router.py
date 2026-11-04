"""Routes du module auth."""

from fastapi import APIRouter, Request, status

from app.core.db import DbSession, TenantDbSession
from app.core.dependencies import CurrentUserId
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
# La limite stricte porte sur (numéro, IP) : un tiers ne peut pas bloquer le
# compte d'un commerçant depuis une seule IP. La limite par numéro seul, plus
# large, freine le brute force distribué sur plusieurs IP.
_LOGIN_FAILS_PER_PHONE_IP = 5  # par minute
_LOGIN_FAILS_PER_PHONE = 20  # par 15 minutes
_LOGIN_PER_IP = 30  # par minute, toutes tentatives
_FORGOT_PER_EMAIL = 3  # par heure
_FORGOT_PER_IP = 10  # par heure
_REGISTER_PER_IP = 10  # par heure
_RESET_PER_IP = 10  # par heure


@router.post(
    "/register",
    response_model=schemas.RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte",
)
async def register(
    payload: schemas.RegisterRequest, db: DbSession, request: Request
) -> schemas.RegisterResponse:
    """Crée un compte utilisateur avec numéro de téléphone + mot de passe. Email optionnel."""
    await rate_limiter.hit(f"register:ip:{client_ip(request)}", _REGISTER_PER_IP, _HOUR)
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
async def login(
    payload: schemas.LoginRequest, db: DbSession, request: Request
) -> schemas.TokenResponse:
    """Authentifie l'utilisateur via numéro de téléphone + mot de passe."""
    ip = client_ip(request)
    # Même normalisation que la recherche en base : une clé ⇔ un compte visé.
    phone = normalize_login_phone(payload.phone_number)
    await rate_limiter.hit(f"login:ip:{ip}", _LOGIN_PER_IP, _MINUTE)
    # Familles de clés aux préfixes distincts ; l'IP (sans « | ») précède le
    # numéro saisi librement, pour qu'aucune saisie ne fabrique la clé d'un autre.
    attempt_keys = (
        (f"login:attempt:phone_ip:{ip}|{phone}", _LOGIN_FAILS_PER_PHONE_IP, _MINUTE),
        (f"login:attempt:phone:{phone}", _LOGIN_FAILS_PER_PHONE, 15 * _MINUTE),
    )
    # La tentative est comptée AVANT la vérification (atomiquement) : des
    # requêtes concurrentes ne peuvent pas toutes passer avant le 1er échec.
    await rate_limiter.hit_many(attempt_keys)

    service = AuthService(db)
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
async def refresh(payload: schemas.RefreshRequest, db: DbSession) -> schemas.TokenResponse:
    """Renouvelle l'access token à partir d'un refresh token valide."""
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post(
    "/forgot-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Demander un email de reset",
)
async def forgot_password(
    payload: schemas.ForgotPasswordRequest, db: DbSession, request: Request
) -> None:
    """Envoie un email de réinitialisation. Renvoie 204 même si l'email n'existe pas."""
    await rate_limiter.hit(f"forgot:ip:{client_ip(request)}", _FORGOT_PER_IP, _HOUR)
    await rate_limiter.hit(f"forgot:email:{payload.email.lower()}", _FORGOT_PER_EMAIL, _HOUR)
    service = AuthService(db)
    await service.send_password_reset(payload.email)


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirmer la réinitialisation",
)
async def reset_password(
    payload: schemas.ResetPasswordRequest, db: DbSession, request: Request
) -> None:
    """Réinitialise le mot de passe via le token reçu par email."""
    await rate_limiter.hit(f"reset:ip:{client_ip(request)}", _RESET_PER_IP, _HOUR)
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


@users_router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer mon compte")
async def delete_me(
    payload: schemas.DeleteAccountRequest, db: TenantDbSession, user_id: CurrentUserId
) -> None:
    """Supprime définitivement le compte, la boutique et toutes ses données (ADR-0011).

    Mot de passe revérifié : 403 s'il est faux.
    """
    await UserService(db).delete_me(user_id, payload.password)
