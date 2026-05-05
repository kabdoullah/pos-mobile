"""Point d'entrée de l'application FastAPI."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import StoreContextMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import router as catalog_router
from app.modules.sales.router import router as sales_router
from app.modules.stores.router import router as stores_router
from app.modules.sync.router import router as sync_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    """Hook de cycle de vie de l'application : startup et shutdown."""
    setup_logging()
    yield


app = FastAPI(
    title="POS Mobile API",
    description="API for the POS Mobile mobile app",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# Middlewares (ordre important : du plus externe au plus interne)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(StoreContextMiddleware)

# Gestion centralisée des exceptions
register_exception_handlers(app)

# Routes
api_v1_prefix = "/api/v1"
app.include_router(auth_router, prefix=f"{api_v1_prefix}/auth", tags=["auth"])
app.include_router(stores_router, prefix=f"{api_v1_prefix}/stores", tags=["stores"])
app.include_router(catalog_router, prefix=f"{api_v1_prefix}/products", tags=["catalog"])
app.include_router(sales_router, prefix=f"{api_v1_prefix}/sales", tags=["sales"])
app.include_router(sync_router, prefix=f"{api_v1_prefix}/sync", tags=["sync"])


def _custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                operation.setdefault("security", [{"BearerAuth": []}])
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check endpoint utilisé par Docker et UptimeRobot."""
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Endpoint racine."""
    return {
        "name": "POS Mobile API",
        "version": app.version,
        "docs": "/docs" if settings.environment != "production" else "disabled",
    }
