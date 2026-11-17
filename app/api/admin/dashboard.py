"""
The Invisible Healer
Admin Dashboard Router

Phase 05 - Jinja Admin Shell

Responsibilities:
    - Render the Admin dashboard.
    - Provide non-sensitive UI metadata.
    - Render allow-listed flash feedback.
    - Keep presentation separate from business logic.

Security:
    - No database records are exposed.
    - No data modification endpoints exist.
    - Authentication is introduced in Phase 06.
    - CSRF verification is introduced before
      enabling form-based mutations.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import DatabaseSessionDependency
from app.services.admin.auth import (
    SESSION_COOKIE_NAME,
    resolve_admin_session,
    session_csrf_token,
)

BASE_DIR = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))


router = APIRouter(prefix="/admin", tags=["Admin"])

DASHBOARD_MODULES = (
    {
        "title": "Medical Concepts",
        "description": (
            "Maintain controlled medical terminology, canonical names, and aliases."
        ),
        "icon": "activity",
        "phase": "Phase 09",
        "status": "planned",
    },
    {
        "title": "Health Issues & Symptoms",
        "description": (
            "Manage health issues, symptoms, and reviewed clinical relationships."
        ),
        "icon": "heart",
        "phase": "Phase 10",
        "status": "planned",
    },
    {
        "title": "Products & Remedies",
        "description": ("Maintain product, remedy, and ingredient catalogs."),
        "icon": "package",
        "phase": "Phase 11",
        "status": "planned",
    },
    {
        "title": "Clinical Documents",
        "description": (
            "Manage versioned evidence documents and their review lifecycle."
        ),
        "icon": "document",
        "phase": "Phase 17",
        "status": "planned",
    },
    {
        "title": "Clinical Protocols",
        "description": (
            "Configure reviewed clinical protocols and safety constraints."
        ),
        "icon": "shield",
        "phase": "Phase 21",
        "status": "planned",
    },
    {
        "title": "Training & Evaluation",
        "description": (
            "Prepare reviewed training examples and held-out evaluation scenarios."
        ),
        "icon": "chart",
        "phase": "Phases 24–25",
        "status": "planned",
    },
)


# ============================================
# ALLOW-LISTED FLASH MESSAGES
# ============================================

# Never render arbitrary query-string content
# as a trusted application notification.

FLASH_MESSAGES = {
    "welcome": {
        "type": "success",
        "message": "Welcome to the Admin dashboard.",
    },
    "unavailable": {
        "type": "info",
        "message": ("This module is not available in the current implementation."),
    },
}


@router.get(
    "", response_class=HTMLResponse, summary="Admin dashboard", name="admin_dashboard"
)
def admin_dashboard(request: Request, db: DatabaseSessionDependency):
    """
    Phase 06 - Protected Admin dashboard.
    Never render Admin content without a
    valid, active, server-side session.
    """
    settings = request.app.state.settings

    if not settings.ADMIN_SESSIONS_ENABLED:
        raise HTTPException(status_code=503, detail="Admin authentication is disabled.")

    authenticated = resolve_admin_session(
        db, request.cookies.get(SESSION_COOKIE_NAME), settings
    )

    if authenticated is None:
        return RedirectResponse(url="/admin/login", status_code=303)

    notice = request.query_params.get("notice")
    flash = FLASH_MESSAGES.get(notice)

    context = {
        "page_title": "Dashboard",
        "active_page": "dashboard",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "modules": DASHBOARD_MODULES,
        "flash": flash,
        "form_errors": (),
        "csrf_token": session_csrf_token(authenticated.session),
        "admin_user": authenticated.user,
    }

    response = templates.TemplateResponse(
        request=request,
        name="admin/dashboard.html",
        context=context,
    )
    response.headers["Cache-Control"] = "no-store, private"

    return response
