"""Service d'envoi d'emails transactionnels via SMTP (aiosmtplib)."""

from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "emails"
_SMTP_SSL_PORT = 465  # SSL direct (implicite) vs 587 STARTTLS


class EmailService:
    """Envoie les emails transactionnels (vérification, reset password) via SMTP."""

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

        message = EmailMessage()
        message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password.get_secret_value() or None,
            start_tls=settings.smtp_use_tls,
            use_tls=not settings.smtp_use_tls and settings.smtp_port == _SMTP_SSL_PORT,
            timeout=10,
        )

    async def send_verification_email(self, to_email: str, user_name: str, raw_token: str) -> None:
        """Envoie le lien de vérification d'adresse email (expire 24h)."""
        link = f"{settings.app_frontend_url}/auth/verify-email?token={raw_token}"
        context = {"user_name": user_name, "link": link, "app_name": settings.smtp_from_name}
        await self._send(
            to_email=to_email,
            subject=f"[{settings.smtp_from_name}] Vérifiez votre adresse email",
            html_body=self._render("verification_email.html", context),
            text_body=self._render("verification_email.txt", context),
        )

    async def send_password_reset_email(
        self, to_email: str, user_name: str, raw_token: str
    ) -> None:
        """Envoie le lien de réinitialisation de mot de passe (expire 1h)."""
        link = f"{settings.app_frontend_url}/auth/reset-password?token={raw_token}"
        context = {"user_name": user_name, "link": link, "app_name": settings.smtp_from_name}
        await self._send(
            to_email=to_email,
            subject=f"[{settings.smtp_from_name}] Réinitialisez votre mot de passe",
            html_body=self._render("password_reset.html", context),
            text_body=self._render("password_reset.txt", context),
        )
