"""Dépendances FastAPI réutilisables (auth, current user, etc.)."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core.exceptions import UnauthorizedError


def get_current_user_id(request: Request) -> UUID:
    """Récupère l'user_id de l'utilisateur authentifié.

    Lève UnauthorizedError si pas de JWT valide. Le middleware
    StoreContextMiddleware a déjà extrait l'user_id depuis le JWT.
    """
    user_id: UUID | None = getattr(request.state, "user_id", None)
    if user_id is None:
        raise UnauthorizedError("Authentication required")
    return user_id


def get_current_store_id(request: Request) -> UUID:
    """Récupère le store_id de l'utilisateur authentifié.

    Lève UnauthorizedError si pas de store associé au JWT (ex: utilisateur
    juste inscrit qui n'a pas encore configuré sa boutique).
    """
    store_id: UUID | None = getattr(request.state, "store_id", None)
    if store_id is None:
        raise UnauthorizedError("Store context required")
    return store_id


# Type aliases pour les routes
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
CurrentStoreId = Annotated[UUID, Depends(get_current_store_id)]
