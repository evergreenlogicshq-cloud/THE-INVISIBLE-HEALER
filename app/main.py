"""
The Invisible Healer
FastAPI Application Entry Point

Phases:
    01 - Application skeleton
    02 - Configuration and secrets
    03 - Database connection lifecycle
    04 - Alembic migration infrastructure
    05 - Jinja Admin shell and static assets

Responsibilities:
    - Create the FastAPI application.
    - Initialize application settings.
    - Manage database engine lifecycle.
    - Register centralized routes.
    - Serve static CSS, JS and images.
    - Register exception handlers.

Architecture:
    Modular FastAPI monolith.

Important:
    - No database tables are created here.
    - No credentials are exposed to templates.
    - Admin authentication belongs to Phase 06.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.db.session import create_database_engine, create_session_factory


logger = logging.getLogger(__name__)

# ============================================
# APPLICATION PATHS
# ============================================
APP_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = APP_DIR / "static"

# ============================================
# APPLICATION FACTORY
# ============================================


def create_app(
    settings: Settings | None = None,
    db_engine: Engine | None = None,
) -> FastAPI:
    """
    Create the FastAPI application.

    Args:
        settings:
            Optional application settings.
            Tests can inject isolated settings.

        db_engine:
            Optional SQLAlchemy engine.
            Tests can inject an SQLite engine.

    Returns:
        Configured FastAPI application.

    Database ownership:
        An internally created engine is disposed
        during application shutdown.

        A caller-provided engine is NOT disposed
        by this application.
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
            - Create or reuse database engine.
            - Initialize session factory.
            - Register infrastructure on app.state.

        Shutdown:
            - Dispose internally owned engine.
            - Preserve externally owned engine.

        Database availability is verified
        separately by /health/ready.
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

    application.state.settings = application_settings
    # ========================================
    # PHASE 05 - STATIC FILES
    # ========================================

    # Starlette serves trusted application
    # assets directly from this directory.
    #
    # Directory structure:
    #   app/static/css/
    #   app/static/js/
    #   app/static/img/
    #
    # Static assets contain no secrets.
    application.mount(
        "/static",
        StaticFiles(
            directory=str(STATIC_DIR),
            check_dir=True,
        ),
        name="static",
    )
    # ========================================
    # APPLICATION ROUTERS
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
