# syntax=docker/dockerfile:1.7
# Multi-stage build pour image finale légère

# ============================================================
# Stage 1 : Builder avec uv
# ============================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Installer les dépendances en cache (couche séparée du code)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copier le code et installer le projet
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ============================================================
# Stage 2 : Runtime minimal
# ============================================================
FROM python:3.12-slim-bookworm AS runtime

# Créer un user non-root pour la sécurité
RUN groupadd --system --gid 1000 app && \
    useradd --system --uid 1000 --gid app --create-home app

WORKDIR /app

# Copier l'environnement Python depuis le builder
COPY --from=builder --chown=app:app /app /app

# Mettre l'environnement uv dans le PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# Healthcheck simple
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
