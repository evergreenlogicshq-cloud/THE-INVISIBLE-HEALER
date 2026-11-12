
"""
The Invisible Healer
Health Check API

Endpoints:
    GET /health/live
    GET /health/ready

Purpose:
    - Liveness verifies that FastAPI can respond.
    - Readiness verifies application initialization.

Phase:
    01 - Project Skeleton

Note:
    Database readiness checks are added in Phase 03.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel


router = APIRouter(prefix="/health", tags=["Health"])


# -----------------------------------------
# Response schemas
# -----------------------------------------

class LivenessResponse(BaseModel):
    """
    Liveness response contract.
    """

    status: str
    service: str


class ReadinessResponse(BaseModel):
    """
    Readiness response contract.
    """

    status: str
    service: str
    checks: dict[str, str]


# -----------------------------------------
# Liveness endpoint
# -----------------------------------------

@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=200,
    summary="Application liveness",
    description=(
        "Check whether the FastAPI "
        "application can respond."
    ),
)
async def health_live(request: Request) -> LivenessResponse:
    """
    Return application liveness.
    Avoid database, AI, storage or network calls.
    A liveness endpoint should stay lightweight.
    """

    return LivenessResponse(status="alive", service=request.app.title)


# -----------------------------------------
# Readiness endpoint
# -----------------------------------------

@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=200,
    summary="Application readiness",
    description=(
        "Check whether the application "
        "configuration is initialized."
    ),
)
async def health_ready(request: Request) -> ReadinessResponse:
    """
    Return Phase 01 application readiness.

    Required configuration was validated during
    app creation and startup.

    Future phases extend readiness with:
        - PostgreSQL connectivity
        - Other required infrastructure checks

    Optional AI providers should not block
    startup unless explicitly required later.
    """

    return ReadinessResponse(
        status="ready",
        service=request.app.title,
        checks={
            "configuration": "ok",
        },
    )
