"""Phase 10 - Shared clinical route utilities."""

import math

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.api.admin.dashboard import templates
from app.schemas.clinical_entities import ClinicalEntityKind
from app.services.admin.auth import AuthenticatedAdmin, session_csrf_token
from app.services.admin.clinical_entities.common import (
    ClinicalEntityConflict,
    ClinicalEntityNotFound,
    ClinicalEntityValidationError,
    list_entities,
    serialize_entity,
)


def service_error(exc: Exception) -> HTTPException:
    """Convert domain errors into safe API responses."""

    if isinstance(exc, ClinicalEntityNotFound):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, ClinicalEntityConflict):
        return HTTPException(status_code=409, detail=str(exc))

    if isinstance(exc, ClinicalEntityValidationError):
        return HTTPException(status_code=422, detail=str(exc))

    raise exc


def render_clinical_page(
    request: Request,
    db: Session,
    authenticated: AuthenticatedAdmin,
    *,
    kind: ClinicalEntityKind,
    page: int,
    query: str | None,
    entity_status: str | None,
):
    """Render a protected clinical catalog page."""

    if kind == "health_issue":
        section = "health-issues"
        title = "Health Issues"
        template_name = "admin/clinical_entities/health_issue.html"
    else:
        section = "symptoms"
        title = "Symptoms"
        template_name = "admin/clinical_entities/symptom.html"

    page_size = 20

    entities, total = list_entities(
        db,
        kind=kind,
        page=page,
        page_size=page_size,
        query=query,
        entity_status=entity_status,
    )

    settings = request.app.state.settings
    context = {
        "page_title": title,
        "active_page": section,
        "section": section,
        "kind": kind,
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "admin_user": authenticated.user,
        "csrf_token": session_csrf_token(authenticated.session),
        "entities": [serialize_entity(item) for item in entities],
        "q": query or "",
        "selected_status": entity_status or "",
        "page": page,
        "pages": max(
            1,
            math.ceil(total / page_size),
        ),
        "total": total,
        "flash": None,
        "form_errors": (),
    }

    response = templates.TemplateResponse(
        request=request, name=template_name, context=context
    )
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response
