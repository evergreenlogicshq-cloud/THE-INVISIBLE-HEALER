"""Phase 08 - Protected audit history endpoint."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from app.api.admin.dashboard import templates
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import DoctorAdminDependency
from app.services.admin.audit import list_audit_events
from app.services.admin.auth import session_csrf_token

router = APIRouter(prefix="/admin", tags=["Admin Audit"])


@router.get(
    "/audit",
    response_class=HTMLResponse,
    name="admin_audit",
    summary="Doctor Admin audit history",
)
def admin_audit_page(
    request: Request,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    page: int = Query(default=1, ge=1, le=200),
    action: str | None = Query(
        default=None,
        max_length=100,
    ),
):
    settings = request.app.state.settings

    page_size = 50
    offset = (page - 1) * page_size

    try:
        results = list_audit_events(
            db,
            limit=page_size + 1,
            offset=offset,
            action=action,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid audit filter",
        ) from exc

    events = results[:page_size]
    has_next = len(results) > page_size

    context = {
        "page_title": "Audit Trail",
        "active_page": "audit",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "admin_user": authenticated.user,
        "csrf_token": session_csrf_token(authenticated.session),
        "events": events,
        "page": page,
        "has_previous": page > 1,
        "has_next": has_next,
        "selected_action": action or "",
        "flash": None,
        "form_errors": (),
    }

    response = templates.TemplateResponse(
        request=request,
        name="admin/audit.html",
        context=context,
    )

    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response
