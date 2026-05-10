"""Cursor-based pagination utilities.

Cursor format: base64url of JSON {"id": "<uuid>", "created_at": "<iso8601>"}.
Opaque to clients — only encode/decode functions should touch the internals.
"""

import base64
import json
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel


def encode_cursor(data: dict[str, object]) -> str:
    """Encode a dict to an opaque base64url cursor token."""
    payload = json.dumps(data, default=str)
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> dict[str, object] | None:
    """Decode a cursor token. Returns None if cursor is empty or malformed."""
    if not cursor:
        return None
    try:
        payload = base64.urlsafe_b64decode(cursor.encode())
        result: dict[str, object] = json.loads(payload)
        return result
    except Exception:
        return None


class CursorPage[T](BaseModel):
    """Generic paginated response with cursor-based navigation."""

    items: list[T]
    next_cursor: str | None
    has_more: bool


class CursorParams:
    """FastAPI dependency that parses cursor pagination query params."""

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        cursor: Annotated[str | None, Query()] = None,
    ) -> None:
        self.limit = limit
        self.cursor = cursor
