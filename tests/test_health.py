"""Tests des endpoints système (/health, /)."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """Le endpoint /health doit répondre 200 OK avec un statut."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert isinstance(data["min_app_build"], int)


@pytest.mark.asyncio
async def test_support_contact_is_public(client: AsyncClient) -> None:
    """Coordonnées du support lisibles sans jeton ; null quand non configurées."""
    with (
        patch.object(settings, "support_contact", "support@pos.ci"),
        patch.object(settings, "support_whatsapp", ""),
    ):
        response = await client.get("/api/v1/support")
    assert response.status_code == 200
    assert response.json() == {"support_contact": "support@pos.ci", "support_whatsapp": None}


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Le endpoint racine doit retourner les infos de l'API."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "POS Mobile API"
