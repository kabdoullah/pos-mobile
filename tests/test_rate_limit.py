"""Tests du rate limiting (limiteur en mémoire + branchement sur les routes d'auth)."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from starlette.requests import Request

from app.core.config import settings
from app.core.exceptions import TooManyRequestsError
from app.core.rate_limit import RateLimiter, client_ip


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _request(forwarded: str | None = None, host: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": (host, 1234)})


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


async def test_limit_reached_then_refused_with_retry_after() -> None:
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_seconds=60)

    clock.now += 20
    with pytest.raises(TooManyRequestsError) as exc:
        await limiter.hit("k", limit=3, window_seconds=60)
    assert exc.value.retry_after == 40


async def test_window_slides() -> None:
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    await limiter.hit("k", limit=2, window_seconds=60)
    clock.now += 30
    await limiter.hit("k", limit=2, window_seconds=60)

    # La 1re requête sort de la fenêtre : une place se libère, pas deux.
    clock.now += 31
    await limiter.hit("k", limit=2, window_seconds=60)
    with pytest.raises(TooManyRequestsError):
        await limiter.hit("k", limit=2, window_seconds=60)


async def test_refused_requests_are_not_counted() -> None:
    clock = _Clock()
    limiter = RateLimiter(clock=clock)
    await limiter.hit("k", limit=1, window_seconds=60)
    for _ in range(5):
        with pytest.raises(TooManyRequestsError):
            await limiter.hit("k", limit=1, window_seconds=60)

    clock.now += 60
    await limiter.hit("k", limit=1, window_seconds=60)


async def test_keys_are_independent() -> None:
    limiter = RateLimiter(clock=_Clock())
    await limiter.hit("a", limit=1, window_seconds=60)
    await limiter.hit("b", limit=1, window_seconds=60)
    with pytest.raises(TooManyRequestsError):
        await limiter.hit("a", limit=1, window_seconds=60)


# ---------------------------------------------------------------------------
# client_ip
# ---------------------------------------------------------------------------


def test_client_ip_ignores_spoofed_left_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert client_ip(_request("6.6.6.6, 41.202.1.2")) == "41.202.1.2"


def test_client_ip_with_two_trusted_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_count", 2)
    assert client_ip(_request("6.6.6.6, 41.202.1.2, 172.16.0.9")) == "41.202.1.2"


def test_client_ip_falls_back_to_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_count", 1)
    assert client_ip(_request(None, host="10.0.0.7")) == "10.0.0.7"
    monkeypatch.setattr(settings, "trusted_proxy_count", 0)
    assert client_ip(_request("41.202.1.2", host="10.0.0.7")) == "10.0.0.7"


# ---------------------------------------------------------------------------
# Routes d'auth
# ---------------------------------------------------------------------------


async def _login(client: AsyncClient, phone: str) -> int:
    response = await client.post(
        "/api/v1/auth/login", json={"phone_number": phone, "password": "wrong-password"}
    )
    return response.status_code


async def test_login_limited_per_phone(client: AsyncClient) -> None:
    for _ in range(5):
        assert await _login(client, "0700000001") == 401

    response = await client.post(
        "/api/v1/auth/login",
        # Même numéro, autre format : même compteur.
        json={"phone_number": "+2250700000001", "password": "wrong-password"},
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0
    assert response.json() == {
        "detail": "Too many requests. Try again later.",
        "code": "RATE_LIMITED",
        "field": None,
    }

    # Un autre compte n'est pas bloqué.
    assert await _login(client, "0700000002") == 401


async def test_forgot_password_limited_per_email_before_any_send(client: AsyncClient) -> None:
    with patch(
        "app.modules.auth.service.AuthService.send_password_reset", new_callable=AsyncMock
    ) as send:
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/forgot-password", json={"email": "awa@example.com"}
            )
            assert response.status_code == 204

        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "AWA@example.com"}
        )

    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert send.await_count == 3
