"""Point d'entrée de l'application FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Hook de cycle de vie de l'application : startup et shutdown."""
    setup_logging()
    yield


app = FastAPI(
    title="POS Mobile CI API",
    description="API for the POS Mobile CI mobile app",
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
app.include_router(stores_router, prefix=f"{api_v1_prefix}/store", tags=["store"])
app.include_router(catalog_router, prefix=f"{api_v1_prefix}/products", tags=["catalog"])
app.include_router(sales_router, prefix=f"{api_v1_prefix}/sales", tags=["sales"])
app.include_router(sync_router, prefix=f"{api_v1_prefix}/sync", tags=["sync"])


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Health check endpoint utilisé par Docker et UptimeRobot."""
    return {"status": "ok", "version": app.version}


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Endpoint racine."""
    return {
        "name": "POS Mobile CI API",
        "version": app.version,
        "docs": "/docs" if settings.environment != "production" else "disabled",
    }
