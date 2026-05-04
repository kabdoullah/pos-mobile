"""Tests des endpoints système (/health, /)."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    """Le endpoint /health doit répondre 200 OK avec un statut."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Le endpoint racine doit retourner les infos de l'API."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "POS Mobile CI API"
