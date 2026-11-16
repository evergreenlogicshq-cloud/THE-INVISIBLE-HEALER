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

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
    "",
    response_class=HTMLResponse,
    summary="Admin dashboard",
    description="Render the Phase 05 Admin presentation shell",
)
def admin_dashboard(request: Request) -> HTMLResponse:
    """
    Render the Admin dashboard.

    This endpoint is intentionally read-only.

    No authentication is implied by this
    demonstration dashboard. Real Admin
    resources require Phase 06 security.
    """
    settings = request.app.state.settings
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
        # Placeholder only.
        # A verified CSRF implementation must
        # replace this before POST forms exist.
        "csrf_token": None,
    }

    return templates.TemplateResponse(
        request=request, name="admin/dashboard.html", context=context
    )
