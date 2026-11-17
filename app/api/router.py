"""
Central API router.

Phases 01-06:
- Health endpoints
- Admin dashboard
- Admin authentication
"""

from fastapi import APIRouter

from app.api.admin.auth import router as admin_auth_router
from app.api.admin.dashboard import router as admin_dashboard_router
from app.api.routes.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(admin_auth_router)
api_router.include_router(admin_dashboard_router)
