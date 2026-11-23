"""
The Invisible Healer
Central API Router

Phases 01-07:
    - Health endpoints
    - Admin authentication
    - Protected Admin dashboard
    - Doctor Administrator directory
"""

from fastapi import APIRouter

from app.api.admin.audit import router as admin_audit_router
from app.api.admin.auth import router as admin_auth_router
from app.api.admin.concepts import router as admin_concepts_router
from app.api.admin.dashboard import router as admin_dashboard_router
from app.api.admin.users import router as admin_users_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(admin_auth_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(admin_users_router)
api_router.include_router(admin_audit_router)
api_router.include_router(admin_concepts_router)
