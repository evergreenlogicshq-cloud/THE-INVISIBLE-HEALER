"""
The Invisible Healer
FastAPI Application Entry Point

Phase 01:
    Application skeleton and architecture.

Phase 02:
    Secrets and configuration hygiene.

Phase 03:
    SQLAlchemy database engine and session lifecycle.

Responsibilities:
    - Application factory
    - Configuration injection
    - Database engine initialization
    - Database session factory initialization
    - Central API router registration
    - Exception handler registration
    - Application startup/shutdown lifecycle
    - Connection pool cleanup
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import create_database_engine, create_session_factory

logger = logging.getLogger(__name__)


# ============================================
# APPLICATION FACTORY
# ============================================


def create_app(
    settings: Settings | None = None, db_engine: Engine | None = None
) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        settings:
            Optional settings override.
            Useful for automated testing.

        db_engine:
            Optional SQLAlchemy Engine override.
            Allows integration and API tests
            to inject an isolated test database.

    Returns:
        Configured FastAPI application.

    Important:
        A caller-provided engine remains owned
        by the caller and is not disposed here.
    """

    application_settings = settings if settings is not None else get_settings()

    # ========================================
    # APPLICATION LIFESPAN
    # ========================================

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """
        Manage database infrastructure lifecycle.

        Startup:
            - Configure engine.
            - Configure session factory.
            - Register infrastructure on app.state.

        Shutdown:
            - Dispose the application's own engine.
            - Release pooled database connections.

        A database connection is not mandatory
        during application startup.

        /health/ready verifies real connectivity.
        """

        logger.info(
            "Starting %s (version %s)",
            application_settings.APP_NAME,
            application_settings.APP_VERSION,
        )

        owns_engine = db_engine is None

        engine = (
            create_database_engine(application_settings) if owns_engine else db_engine
        )

        application.state.db_engine = engine
        application.state.db_session_factory = create_session_factory(engine)
        logger.info("Database infrastructure initialized.")

        try:
            yield

        finally:
            if owns_engine:
                engine.dispose()

                logger.info("Database connection pool disposed.")

            logger.info("Stopping %s", application_settings.APP_NAME)

    # ========================================
    # FASTAPI CONFIGURATION
    # ========================================

    enable_docs = not application_settings.is_production

    application = FastAPI(
        title=application_settings.APP_NAME,
        version=application_settings.APP_VERSION,
        description=("The Invisible Healer - Data-first clinical AI backend."),
        debug=(application_settings.DEBUG and not application_settings.is_production),
        docs_url=("/docs" if enable_docs else None),
        redoc_url=("/redoc" if enable_docs else None),
        openapi_url=("/openapi.json" if enable_docs else None),
        lifespan=lifespan,
    )
    # ========================================
    # APPLICATION STATE
    # ========================================
    application.state.settings = application_settings
    # ========================================
    # API ROUTERS
    # ========================================
    application.include_router(api_router)
    # ========================================
    # EXCEPTION HANDLERS
    # ========================================
    register_exception_handlers(application)

    return application


# ============================================
# DEFAULT ASGI APPLICATION
# ============================================

app = create_app()
