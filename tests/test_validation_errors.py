"""Format des erreurs 422 : `{detail, code, field}` plat, attendu par le mobile et le backoffice."""

import logging

import pytest
from httpx import AsyncClient


async def test_request_validation_error_is_flat(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "phone_number": "+2250000000000",
            "password": "secret123",
            "email": "user@example.com",
        },
    )
    assert resp.status_code == 422
    assert resp.json() == {
        "detail": "Phone number does not exist (check the number of digits and prefix).",
        "code": "VALIDATION_ERROR",
        "field": "phone_number",
    }


async def test_validation_error_does_not_log_input(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"phone_number": "+2250700000001", "password": "Zq9#x", "email": "user@example.com"},
    )
    assert resp.status_code == 422
    assert resp.json()["field"] == "password"
    assert "Zq9#x" not in caplog.text
    assert all("Zq9#x" not in str(r.__dict__) for r in caplog.records)
