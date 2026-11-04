"""Tests des routes du deep link Android (assetlinks + page de secours)."""

import pytest
from httpx import AsyncClient

from app.core.config import settings

_FINGERPRINT = "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"


async def test_assetlinks_declares_configured_app(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages = ["ci.pos.macaisse", "ci.pos.macaisse.dev"]
    monkeypatch.setattr(settings, "android_package_names", packages)
    monkeypatch.setattr(settings, "android_cert_sha256_fingerprints", [_FINGERPRINT])

    response = await client.get("/.well-known/assetlinks.json")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package,
                "sha256_cert_fingerprints": [_FINGERPRINT],
            },
        }
        for package in packages
    ]


async def test_assetlinks_empty_when_not_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "android_package_names", ["ci.pos.macaisse"])
    monkeypatch.setattr(settings, "android_cert_sha256_fingerprints", [])

    response = await client.get("/.well-known/assetlinks.json")

    assert response.status_code == 200
    assert response.json() == []


async def test_reset_password_fallback_page_never_echoes_token(client: AsyncClient) -> None:
    token = "secret-reset-token-123"

    response = await client.get("/auth/reset-password", params={"token": token})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert token not in response.text
    assert "téléphone" in response.text
