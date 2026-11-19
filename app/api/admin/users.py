"""
Phase 07 - Doctor Administrator Directory.

Endpoints:
    GET /admin/users

Only an authenticated Doctor Admin can access
this page.

There is no role assignment API because every
administrator belongs to the Doctor Admin type.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app.api.admin.dashboard import templates
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import (
    ADMIN_TYPE,
    DoctorAdminDependency,
    get_doctor_capabilities,
)
from app.models.admin.admin_user import AdminUser
from app.services.admin.auth import session_csrf_token

router = APIRouter(prefix="/admin", tags=["Doctor Administration"])


@router.get(
    "/users",
    response_class=HTMLResponse,
    name="admin_users",
    summary="Doctor administrator directory",
)
def admin_users_page(
    request: Request,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
):
    """
    Display all administrator identities.

    Security:
        - Active authenticated Doctor Admin required.
        - No password hashes are displayed.
        - No session tokens are displayed.
        - No role assignment functionality exists.
        - Browser caching is disabled.
    """

    settings = request.app.state.settings

    users = db.scalars(
        select(AdminUser).order_by(
            AdminUser.created_at.desc(),
            AdminUser.id,
        )
    ).all()
    context = {
        "page_title": "Doctor Administrators",
        "active_page": "users",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "admin_user": authenticated.user,
        "csrf_token": session_csrf_token(authenticated.session),
        "flash": None,
        "form_errors": (),
        "users": users,
        "admin_type": ADMIN_TYPE,
        "capabilities": get_doctor_capabilities,
    }

    response = templates.TemplateResponse(
        request=request, name="admin/users.html", context=context
    )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response
