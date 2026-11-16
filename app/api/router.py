"""
The Invisible Healer
Central API Router

Responsibilities:
    - Register API route modules.
    - Maintain centralized route composition.
    - Keep the application entry point minimal.

Phase:
    01 - Project Skeleton
    05 - Admin dashboard integration

Responsibilities:
    - Centralize route registration.
    - Separate public health endpoints
      from Admin presentation endpoints.
    - Keep app/main.py independent of
      individual feature routers.
"""

from fastapi import APIRouter

from app.api.admin.dashboard import router as admin_dashboard_router
from app.api.routes.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(admin_dashboard_router)
