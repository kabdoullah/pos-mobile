"""Emails transactionnels : contenu (`EmailService`) séparé du transport (`EmailSender`).

`EmailService` prépare le contenu (templates, liens, sujets) et délègue l'envoi à
un `EmailSender` injecté. Changer de provider = ajouter une implémentation
d'`EmailSender` et la câbler dans `get_email_service`, sans toucher au contenu.

Brevo passe par HTTP sur le port 443 : le SMTP est bloqué chez la plupart des
hébergeurs. L'expéditeur (`MAIL_FROM_EMAIL`) doit être validé dans Brevo
(Senders) ; sans domaine à soi, une adresse Gmail validée convient mais finit
plus souvent en spam.
"""

from pathlib import Path
from typing import Protocol

import httpx
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"
_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"

logger = structlog.get_logger()


class EmailSendError(Exception):
    """Échec d'envoi côté provider — porte le status HTTP et le corps de réponse."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Email provider send failed: {status_code} — {body}")


class EmailSender(Protocol):
    """Transport d'un email déjà rendu (provider, no-op, faux de test…)."""

    async def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> None:
        """Envoie l'email ; lève une exception si le provider le refuse."""
        ...


class BrevoEmailSender:
    """Envoi via l'API HTTP Brevo."""

    def __init__(self, api_key: str, from_email: str, from_name: str) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._from_name = from_name

    async def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> None:
        """POST sur l'API Brevo ; lève `EmailSendError` si elle répond en erreur."""
        payload = {
            "sender": {"name": self._from_name, "email": self._from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _BREVO_SEND_URL,
                json=payload,
                headers={"api-key": self._api_key},
                timeout=10,
            )
            if response.is_error:
                # Le corps Brevo explique la cause exacte (expéditeur non validé,
                # clé invalide, compte pas encore activé…).
                raise EmailSendError(response.status_code, response.text)


class NullEmailSender:
    """N'envoie rien : utilisé quand `EMAIL_ENABLED=false` (dev, CI)."""

    async def send(self, to_email: str, subject: str, html_body: str, text_body: str) -> None:  # noqa: ARG002 (signature du Protocol)
        """Ignore l'email, en le signalant : en prod, c'est une erreur de config."""
        logger.warning("email_not_sent_disabled", subject=subject)


class EmailService:
    """Prépare les emails transactionnels (vérification, reset password) et les envoie."""

    def __init__(self, sender: EmailSender) -> None:
        self._sender = sender
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def _render(self, template_name: str, context: dict[str, str]) -> str:
        return self._env.get_template(template_name).render(**context)

    async def send_verification_email(self, to_email: str, user_name: str, raw_token: str) -> None:
        """Envoie le lien de vérification d'adresse email (expire 24h)."""
        # Token dans le fragment (#), comme pour le reset : absent des logs d'accès.
        link = f"{settings.app_frontend_url}/auth/verify-email#token={raw_token}"
        context = {"user_name": user_name, "link": link, "app_name": settings.mail_from_name}
        await self._sender.send(
            to_email=to_email,
            subject=f"[{settings.mail_from_name}] Vérifiez votre adresse email",
            html_body=self._render("verification_email.html", context),
            text_body=self._render("verification_email.txt", context),
        )

    async def send_password_reset_email(
        self, to_email: str, user_name: str, raw_token: str
    ) -> None:
        """Envoie le lien de réinitialisation de mot de passe (expire 1h)."""
        link = password_reset_link(raw_token)
        context = {"user_name": user_name, "link": link, "app_name": settings.mail_from_name}
        await self._sender.send(
            to_email=to_email,
            subject=f"[{settings.mail_from_name}] Réinitialisez votre mot de passe",
            html_body=self._render("password_reset.html", context),
            text_body=self._render("password_reset.txt", context),
        )


def password_reset_link(raw_token: str) -> str:
    """Lien de réinitialisation (email ou transmis par le support, ADR-0014).

    Token dans le fragment (#) : jamais envoyé au serveur par le navigateur,
    il n'apparaît donc dans aucun log d'accès (page de secours, proxys).
    L'app le lit depuis l'App Link.
    """
    return f"{settings.app_frontend_url}/auth/reset-password#token={raw_token}"


def get_email_service() -> EmailService:
    """Point de câblage unique : choisit le transport selon la config.

    Dépendance FastAPI (surchargeable via `app.dependency_overrides`).
    """
    sender: EmailSender
    if settings.email_enabled:
        sender = BrevoEmailSender(
            api_key=settings.brevo_api_key.get_secret_value(),
            from_email=settings.mail_from_email,
            from_name=settings.mail_from_name,
        )
    else:
        sender = NullEmailSender()
    return EmailService(sender)
