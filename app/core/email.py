"""Service d'envoi d'emails transactionnels via l'API HTTP Brevo.

HTTP sur le port 443 : le SMTP est bloqué chez la plupart des hébergeurs.
L'expéditeur (`MAIL_FROM_EMAIL`) doit être validé dans Brevo (Senders) ;
sans domaine à soi, une adresse Gmail validée convient mais finit plus
souvent en spam.
"""

from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"
_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


class EmailSendError(Exception):
    """Échec d'envoi côté provider — porte le status HTTP et le corps de réponse."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"Email provider send failed: {status_code} — {body}")


class EmailService:
    """Envoie les emails transactionnels (vérification, reset password) via Brevo."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )

    def _render(self, template_name: str, context: dict[str, str]) -> str:
        return self._env.get_template(template_name).render(**context)

    async def _send(self, to_email: str, subject: str, html_body: str, text_body: str) -> None:
        if not settings.email_enabled:
            return

        payload = {
            "sender": {"name": settings.mail_from_name, "email": settings.mail_from_email},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                _BREVO_SEND_URL,
                json=payload,
                headers={"api-key": settings.brevo_api_key.get_secret_value()},
                timeout=10,
            )
            if response.is_error:
                # Le corps Brevo explique la cause exacte (expéditeur non validé,
                # clé invalide, compte pas encore activé…).
                raise EmailSendError(response.status_code, response.text)

    async def send_verification_email(self, to_email: str, user_name: str, raw_token: str) -> None:
        """Envoie le lien de vérification d'adresse email (expire 24h)."""
        link = f"{settings.app_frontend_url}/auth/verify-email?token={raw_token}"
        context = {"user_name": user_name, "link": link, "app_name": settings.mail_from_name}
        await self._send(
            to_email=to_email,
            subject=f"[{settings.mail_from_name}] Vérifiez votre adresse email",
            html_body=self._render("verification_email.html", context),
            text_body=self._render("verification_email.txt", context),
        )

    async def send_password_reset_email(
        self, to_email: str, user_name: str, raw_token: str
    ) -> None:
        """Envoie le lien de réinitialisation de mot de passe (expire 1h)."""
        # Token dans le fragment (#) : jamais envoyé au serveur par le navigateur,
        # il n'apparaît donc dans aucun log d'accès (page de secours, proxys).
        # L'app le lit depuis l'App Link.
        link = f"{settings.app_frontend_url}/auth/reset-password#token={raw_token}"
        context = {"user_name": user_name, "link": link, "app_name": settings.mail_from_name}
        await self._send(
            to_email=to_email,
            subject=f"[{settings.mail_from_name}] Réinitialisez votre mot de passe",
            html_body=self._render("password_reset.html", context),
            text_body=self._render("password_reset.txt", context),
        )
