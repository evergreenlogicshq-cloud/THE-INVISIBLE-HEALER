
"""
The Invisible Healer
FastAPI Application Entry Point

Phase 01 - Project Skeleton

Responsibilities:
    - Application factory
    - Central API router registration
    - Exception handler registration
    - Startup and shutdown lifecycle
    - Environment-specific API documentation
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create a configured FastAPI application.
    Settings can be injected for isolated testing.
    """

    application_settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Manage application startup and shutdown."""

        logger.info(
            "Starting %s (version %s)",
            application_settings.APP_NAME,
            application_settings.APP_VERSION,
        )

        yield

        logger.info("Stopping %s", application_settings.APP_NAME)

    enable_docs = not application_settings.is_production
    application = FastAPI(
        title=application_settings.APP_NAME,
        version=application_settings.APP_VERSION,
        description=(
            "The Invisible Healer - "
            "Data-first clinical AI backend."
        ),
        debug=(
            application_settings.DEBUG
            and not application_settings.is_production
        ),
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url=(
            "/openapi.json" if enable_docs else None
        ),
        lifespan=lifespan,
    )

    application.state.settings = application_settings
    application.include_router(api_router)
    register_exception_handlers(application)

    return application


# Default ASGI application for Uvicorn.
app = create_app()
