"""Middlewares applicatifs."""

from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.security import decode_token


class StoreContextMiddleware(BaseHTTPMiddleware):
    """Extrait le store_id du JWT et l'injecte dans request.state.

    Cette information est ensuite consommée par get_tenant_db() pour activer
    le Row-Level Security PostgreSQL. Voir docs/adr/0002-multi-tenancy-rls.md.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.user_id = None
        request.state.store_id = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                user_id = payload.get("sub")
                store_id = payload.get("store_id")
                if user_id:
                    request.state.user_id = UUID(user_id)
                if store_id:
                    request.state.store_id = UUID(store_id)

        response: Response = await call_next(request)
        return response
