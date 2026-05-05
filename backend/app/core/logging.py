"""Configuration des logs structurés via structlog."""

import logging
import sys

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """Configure le logging structlog pour l'application."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.environment == "local":
        # Logs lisibles en couleur en dev local
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        # JSON en staging et prod (parsable par les agrégateurs de logs)
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
