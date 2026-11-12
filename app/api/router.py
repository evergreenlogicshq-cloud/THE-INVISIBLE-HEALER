
"""
The Invisible Healer
Central API Router

Responsibilities:
    - Register API route modules.
    - Maintain centralized route composition.
    - Keep the application entry point minimal.

Phase:
    01 - Project Skeleton
"""

from fastapi import APIRouter
from app.api.routes.health import router as health_router


api_router = APIRouter()

api_router.include_router(health_router)

