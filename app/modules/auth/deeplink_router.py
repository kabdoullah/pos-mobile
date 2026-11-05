"""Routes publiques des liens envoyés par email (App Links, reset, vérification).

Montées à la racine, hors `/api/v1` : Android vérifie `/.well-known/assetlinks.json`
sur le domaine du lien, et l'URL de l'email doit rester une URL https cliquable.
"""

from html import escape
from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.core.config import settings

router = APIRouter(include_in_schema=False)


@router.get("/.well-known/assetlinks.json")
async def assetlinks() -> list[dict[str, Any]]:
    """Déclare les apps Android autorisées à ouvrir les liens de ce domaine.

    Android ne vérifie que la présence de l'empreinte de l'app parmi celles
    listées : partager la liste entre les packages est sans risque.
    """
    if not settings.android_cert_sha256_fingerprints:
        return []
    return [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package_name,
                "sha256_cert_fingerprints": settings.android_cert_sha256_fingerprints,
            },
        }
        for package_name in settings.android_package_names
    ]


@router.get("/auth/reset-password", response_class=HTMLResponse)
async def reset_password_fallback() -> HTMLResponse:
    """Page affichée quand le lien est ouvert hors de l'app (PC, app absente).

    Ne réaffiche jamais le token, et `no-referrer` évite qu'il fuite vers un
    site tiers via l'en-tête Referer.
    """
    app_name = escape(settings.mail_from_name)
    body = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Réinitialisation du mot de passe</title>
</head>
<body style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;line-height:1.5;">
  <h1 style="font-size:1.4em;">{app_name}</h1>
  <p>Pour choisir un nouveau mot de passe, ouvrez ce lien depuis le téléphone
  où l'application est installée.</p>
  <p>Si l'application est installée et que cette page s'affiche quand même,
  mettez-la à jour depuis le Play Store puis rouvrez le lien de l'email.</p>
  <p style="color:#6b7280;font-size:0.9em;">Le lien expire 1 heure après la demande.</p>
</body>
</html>"""
    return HTMLResponse(content=body, headers={"Referrer-Policy": "no-referrer"})


@router.get("/auth/verify-email", response_class=HTMLResponse)
async def verify_email_page() -> HTMLResponse:
    """Page de confirmation d'adresse email ouverte depuis le lien de l'email.

    Le token est lu dans le fragment (#token=…) et envoyé seulement au clic :
    les scanners de liens des messageries, qui suivent les URL sans cliquer,
    ne valident donc pas l'adresse à la place de son propriétaire.
    """
    app_name = escape(settings.mail_from_name)
    body = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vérification de l'adresse email</title>
</head>
<body style="font-family:sans-serif;max-width:480px;margin:auto;padding:24px;line-height:1.5;">
  <h1 style="font-size:1.4em;">{app_name}</h1>
  <p id="msg">Confirmez votre adresse email pour pouvoir réinitialiser votre mot de passe
  en cas d'oubli.</p>
  <button id="confirm" type="button"
    style="font-size:1em;padding:12px 20px;border:0;border-radius:8px;background:#b4532a;color:#fff;">
    Confirmer mon adresse</button>
  <script>
    const token = new URLSearchParams(location.hash.slice(1)).get("token");
    const msg = document.getElementById("msg");
    const btn = document.getElementById("confirm");
    history.replaceState(null, "", location.pathname);
    if (!token) {{
      msg.textContent = "Lien incomplet. Rouvrez le lien reçu par email.";
      btn.hidden = true;
    }}
    btn.addEventListener("click", async () => {{
      btn.disabled = true;
      try {{
        const r = await fetch("/api/v1/auth/verify-email", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ token }}),
        }});
        btn.hidden = r.ok;
        msg.textContent = r.ok
          ? "Adresse email confirmée. Vous pouvez fermer cette page."
          : r.status === 429
            ? "Trop de tentatives. Réessayez dans une heure."
            : "Lien invalide ou expiré. Demandez un nouvel email depuis l'application.";
      }} catch (e) {{
        msg.textContent = "Erreur réseau. Vérifiez votre connexion puis réessayez.";
      }} finally {{
        btn.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=body, headers={"Referrer-Policy": "no-referrer"})
