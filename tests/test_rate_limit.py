"""Tests du rate limiting (limiteur en mémoire + branchement sur les routes d'auth)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import settings
from app.core.exceptions import TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import RateLimiter, client_ip, rate_limiter
from app.core.security import hash_password
from tests.factories import create_user_with_store

_PASSWORD = "motdepasse123"


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


async def test_hit_many_is_all_or_nothing() -> None:
    limiter = RateLimiter(clock=_Clock())
    await limiter.hit("full", limit=1, window_seconds=60)

    # « full » est plein : « free » ne doit pas être compté non plus.
    with pytest.raises(TooManyRequestsError):
        await limiter.hit_many([("free", 1, 60), ("full", 1, 60)])
    await limiter.hit("free", limit=1, window_seconds=60)


async def test_clear_forgets_key() -> None:
    limiter = RateLimiter(clock=_Clock())
    await limiter.hit("k", limit=1, window_seconds=60)
    await limiter.clear("k")
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


async def _login(
    client: AsyncClient,
    phone: str,
    password: str = "wrong-password",
    ip: str = "41.0.0.1",
) -> int:
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone_number": phone, "password": password},
        headers={"X-Forwarded-For": ip},
    )
    return response.status_code


async def test_login_failures_limited_per_phone_and_ip(client: AsyncClient) -> None:
    for _ in range(5):
        assert await _login(client, "0700000001") == 401

    response = await client.post(
        "/api/v1/auth/login",
        # Même numéro, autre format : même compteur.
        json={"phone_number": "+2250700000001", "password": "wrong-password"},
        headers={"X-Forwarded-For": "41.0.0.1"},
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


async def test_third_party_cannot_lock_account_from_one_ip(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user, _ = await create_user_with_store(db_session, "victime@example.com")
    user.password_hash = hash_password(_PASSWORD)
    await db_session.flush()

    clock = _Clock()
    monkeypatch.setattr(rate_limiter, "_clock", clock)

    # L'attaquant s'acharne depuis une IP pendant 14 minutes.
    for _ in range(7):
        for _ in range(10):
            await _login(client, user.phone_number, ip="6.6.6.6")
        clock.now += 2 * 60
    assert await _login(client, user.phone_number, ip="6.6.6.6") == 429

    # Il n'a apporté que 5 échecs au compteur du numéro : le commerçant, depuis
    # son propre réseau, se connecte toujours.
    assert await _login(client, user.phone_number, _PASSWORD, ip="41.0.0.9") == 200


async def test_login_success_resets_failures(client: AsyncClient, db_session: AsyncSession) -> None:
    user, _ = await create_user_with_store(db_session, "oubli@example.com")
    user.password_hash = hash_password(_PASSWORD)
    await db_session.flush()

    for _ in range(4):
        assert await _login(client, user.phone_number) == 401
    assert await _login(client, user.phone_number, _PASSWORD) == 200

    # Compteur remis à zéro : 5 nouvelles erreurs de saisie sont permises.
    for _ in range(5):
        assert await _login(client, user.phone_number) == 401
    assert await _login(client, user.phone_number) == 429


async def test_concurrent_login_burst_is_limited(client: AsyncClient) -> None:
    async def slow_failure(*_: object) -> None:
        await asyncio.sleep(0.05)  # vérification du mot de passe en cours
        raise UnauthorizedError("Invalid phone number or password.")

    with patch("app.modules.auth.service.AuthService.login", new=slow_failure):
        statuses = await asyncio.gather(*(_login(client, "0700000004") for _ in range(10)))

    # Sans comptage préalable, les 10 passeraient la vérification ensemble.
    assert statuses.count(401) == 5
    assert statuses.count(429) == 5


async def test_unexpected_error_keeps_attempt_counted(client: AsyncClient) -> None:
    async def crash(*_: object) -> None:
        raise RuntimeError("panne base de données")

    with patch("app.modules.auth.service.AuthService.login", new=crash):
        for _ in range(5):
            with pytest.raises(RuntimeError):
                await _login(client, "0700000005")

    # Les erreurs imprévues n'ont pas remis le compteur à zéro.
    assert await _login(client, "0700000005") == 429


async def test_login_failures_limited_per_phone_across_ips(client: AsyncClient) -> None:
    # Brute force distribué : 5 échecs depuis chacune de 10 IP = 50 échecs.
    for i in range(10):
        for _ in range(5):
            assert await _login(client, "0700000003", ip=f"41.0.1.{i}") == 401
    assert await _login(client, "0700000003", ip="41.0.2.1") == 429


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
