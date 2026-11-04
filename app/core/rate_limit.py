"""Rate limiting en mémoire (fenêtre glissante) des endpoints publics sensibles.

Stockage dans le process : juste tant que l'API tourne en un seul process
uvicorn (cf. `scripts/entrypoint.sh`). Les compteurs repartent à zéro au
redémarrage ; passer à un stockage partagé avant de lancer plusieurs instances.
"""

import asyncio
import math
import time
from collections import deque
from collections.abc import Callable, Sequence

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import TooManyRequestsError

# Purge des clés inactives toutes les N requêtes : borne la mémoire sans tâche de fond.
_SWEEP_EVERY = 1000


class RateLimiter:
    """Compte les requêtes par clé sur une fenêtre glissante."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._windows: dict[str, float] = {}
        self._calls = 0
        self._lock = asyncio.Lock()

    async def hit(self, key: str, limit: int, window_seconds: float) -> None:
        """Enregistre une requête pour `key`.

        Lève `TooManyRequestsError` si `limit` requêtes ont déjà eu lieu sur les
        `window_seconds` dernières secondes ; la requête refusée n'est pas comptée.
        """
        await self.hit_many([(key, limit, window_seconds)])

    async def hit_many(self, limits: Sequence[tuple[str, int, float]]) -> None:
        """Enregistre une requête sur plusieurs clés `(key, limit, window_seconds)`.

        Atomique : soit toutes les clés ont de la place et la requête est
        comptée sur chacune, soit `TooManyRequestsError` est levée et rien
        n'est compté. Compter avant de traiter la requête empêche une rafale
        de requêtes concurrentes de passer avant que la première soit comptée.
        """
        async with self._lock:
            now = self._clock()
            active = [
                (self._active_hits(key, window, now), limit, window)
                for key, limit, window in limits
            ]
            for hits, limit, window in active:
                self._raise_if_full(hits, limit, window, now)
            for hits, _, _ in active:
                hits.append(now)

    async def clear(self, key: str) -> None:
        """Oublie le compteur de `key` (ex. login réussi)."""
        async with self._lock:
            self._hits.pop(key, None)
            self._windows.pop(key, None)

    def _active_hits(self, key: str, window_seconds: float, now: float) -> deque[float]:
        """Hits de `key` encore dans la fenêtre (purge les expirés au passage)."""
        self._calls += 1
        if self._calls % _SWEEP_EVERY == 0:
            self._sweep(now)
        hits = self._hits.setdefault(key, deque())
        self._windows[key] = window_seconds
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()
        return hits

    @staticmethod
    def _raise_if_full(hits: deque[float], limit: int, window_seconds: float, now: float) -> None:
        if len(hits) >= limit:
            retry_after = hits[0] + window_seconds - now
            raise TooManyRequestsError(retry_after=max(1, math.ceil(retry_after)))

    def reset(self) -> None:
        """Oublie tous les compteurs (tests)."""
        self._hits.clear()
        self._windows.clear()
        self._calls = 0

    def _sweep(self, now: float) -> None:
        stale = [
            k for k, hits in self._hits.items() if not hits or hits[-1] <= now - self._windows[k]
        ]
        for key in stale:
            del self._hits[key]
            del self._windows[key]


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    """IP du client telle que vue par le proxy de confiance.

    Avec `client_ip_header` (ex. `cf-connecting-ip` derrière Cloudflare), on lit
    cet en-tête, que le proxy écrase. Sinon, `X-Forwarded-For` : les proxys
    ajoutent l'IP de leur interlocuteur à droite, les entrées de gauche viennent
    du client et sont falsifiables ; on lit la `trusted_proxy_count`-ième en
    partant de la droite.
    """
    if settings.client_ip_header:
        header_ip = request.headers.get(settings.client_ip_header, "").strip()
        if header_ip:
            return header_ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and settings.trusted_proxy_count > 0:
        hops = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if hops:
            return hops[-min(settings.trusted_proxy_count, len(hops))]
    return request.client.host if request.client else "unknown"
