"""
The Invisible Healer
Health Check API

Phase 01:
    Application liveness and configuration checks.

Phase 03:
    Real PostgreSQL database readiness.

Endpoints:
    GET /health/live
    GET /health/ready

Rules:
    - Liveness does not query the database.
    - Readiness verifies real DB connectivity.
    - DB errors return HTTP 503.
    - Database credentials are never returned.
    - Infrastructure errors are not exposed
      to the public HTTP response.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import check_database_connection

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/health", tags=["Health"])


# ============================================
# RESPONSE SCHEMAS
# ============================================


class LivenessResponse(BaseModel):
    """
    Application liveness response.
    """

    status: str
    service: str


class ReadinessResponse(BaseModel):
    """
    Application readiness response.
    """

    status: str
    service: str
    checks: dict[str, str]


# ============================================
# LIVENESS ENDPOINT
# ============================================


@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=200,
    summary="Application liveness",
)
def health_live(request: Request) -> LivenessResponse:
    """
    Verify that FastAPI is responding.

    This must remain independent of:
        - PostgreSQL
        - Supabase Storage
        - OpenAI
        - Any external AI provider

    Liveness failure generally means
    the application process is unhealthy.
    """

    return LivenessResponse(status="alive", service=request.app.title)


# ============================================
# READINESS ENDPOINT
# ============================================


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={
        503: {
            "model": ReadinessResponse,
            "description": ("Required database unavailable."),
        },
    },
    summary="Application readiness",
)
def health_ready(request: Request) -> ReadinessResponse | JSONResponse:
    """
    Check required application infrastructure.

    Readiness verifies:
        1. Application configuration exists.
        2. SQLAlchemy engine is initialized.
        3. PostgreSQL accepts a query.

    Returns:
        200:
            Application is ready.

        503:
            Required database is unavailable.

    The client never receives raw DB errors.
    """

    checks = {"configuration": "ok"}
    engine = getattr(request.app.state, "db_engine", None)

    if engine is None:
        checks["database"] = "unavailable"

        return JSONResponse(
            status_code=503,
            content=ReadinessResponse(
                status="not_ready",
                service=request.app.title,
                checks=checks,
            ).model_dump(),
        )

    try:
        connected = check_database_connection(engine)

        if not connected:
            checks["database"] = "unavailable"

            return JSONResponse(
                status_code=503,
                content=ReadinessResponse(
                    status="not_ready",
                    service=request.app.title,
                    checks=checks,
                ).model_dump(),
            )

    except (SQLAlchemyError, OSError, TimeoutError):
        logger.warning("Database readiness check failed.")
        checks["database"] = "unavailable"

        return JSONResponse(
            status_code=503,
            content=ReadinessResponse(
                status="not_ready",
                service=request.app.title,
                checks=checks,
            ).model_dump(),
        )

    checks["database"] = "ok"

    return ReadinessResponse(status="ready", service=request.app.title, checks=checks)
