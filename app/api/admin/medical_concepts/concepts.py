"""Phase 09 - Protected medical concept endpoints."""

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Form, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.api.admin.dashboard import templates
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import DoctorAdminDependency
from app.schemas.medical_concepts.concept import (
    ConceptKind,
    ConceptList,
    ConceptRead,
    ConceptStatus,
    ConceptWrite,
)
from app.services.admin.auth import session_csrf_token, verify_session_csrf
from app.services.admin.medical_concepts.concepts import (
    ConceptConflict,
    ConceptNotFound,
    ConceptValidationError,
    create_concept,
    get_concept,
    list_concepts,
    retire_concept,
    serialize_concept,
    update_concept,
)

router = APIRouter(tags=["Medical Concepts"])


def require_csrf(authenticated, token: str | None) -> None:
    if not token or not verify_session_csrf(authenticated.session, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token."
        )


def service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ConceptNotFound):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, ConceptConflict):
        return HTTPException(status_code=409, detail=str(exc))

    if isinstance(exc, ConceptValidationError):
        return HTTPException(status_code=422, detail=str(exc))

    raise exc


def parse_form(
    *,
    kind: str,
    namespace: str,
    canonical_name: str,
    ontology_code: str,
    concept_status: str,
    aliases: str,
) -> ConceptWrite:
    return ConceptWrite(
        kind=kind,
        namespace=namespace,
        canonical_name=canonical_name,
        ontology_code=ontology_code,
        status=concept_status,
        aliases=[item.strip() for item in aliases.splitlines() if item.strip()],
    )


def form_error_response(request: Request, message: str, status_code: int):
    """Return a safe, plain error without reflecting HTML."""

    return HTMLResponse(
        content=(
            "<!DOCTYPE html><html lang='en'>"
            "<head><meta charset='utf-8'>"
            "<title>Concept Error</title></head>"
            "<body><h1>Concept could not be saved</h1>"
            "<p>Check the submitted terminology or "
            "contact the administrator.</p>"
            "<a href='/admin/concepts'>Back to concepts</a>"
            "</body></html>"
        ),
        status_code=status_code,
        headers={"Cache-Control": "no-store"},
    )


# ==========================================
# JSON API
# ==========================================


@router.get("/api/admin/concepts", response_model=ConceptList, name="api_list_concepts")
def api_list_concepts(
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=25, ge=1, le=100),
    kind: ConceptKind | None = None,
    concept_status: Annotated[
        ConceptStatus | None,
        Query(alias="status"),
    ] = None,
    q: str | None = Query(default=None, max_length=200),
):
    items, total = list_concepts(
        db,
        page=page,
        page_size=page_size,
        kind=kind,
        status=concept_status,
        query=q,
    )

    return ConceptList(
        items=[serialize_concept(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/api/admin/concepts/{concept_id}",
    response_model=ConceptRead,
    name="api_get_concept",
)
def api_get_concept(
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
):
    try:
        return serialize_concept(get_concept(db, concept_id))
    except ConceptNotFound as exc:
        raise service_error(exc) from exc


@router.post(
    "/api/admin/concepts",
    response_model=ConceptRead,
    status_code=201,
    name="api_create_concept",
)
def api_create_concept(
    request: Request,
    data: ConceptWrite,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: str | None = Header(default=None),
):
    require_csrf(authenticated, x_csrf_token)

    try:
        concept = create_concept(
            db,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )
        return serialize_concept(concept)

    except (ConceptConflict, ConceptValidationError) as exc:
        raise service_error(exc) from exc


@router.put(
    "/api/admin/concepts/{concept_id}",
    response_model=ConceptRead,
    name="api_update_concept",
)
def api_update_concept(
    request: Request,
    concept_id: uuid.UUID,
    data: ConceptWrite,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: str | None = Header(default=None),
):
    require_csrf(authenticated, x_csrf_token)

    try:
        concept = update_concept(
            db,
            concept_id=concept_id,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )
        return serialize_concept(concept)

    except (
        ConceptNotFound,
        ConceptConflict,
        ConceptValidationError,
    ) as exc:
        raise service_error(exc) from exc


@router.delete(
    "/api/admin/concepts/{concept_id}",
    response_model=ConceptRead,
    name="api_retire_concept",
)
def api_retire_concept(
    request: Request,
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: str | None = Header(default=None),
):
    require_csrf(authenticated, x_csrf_token)

    try:
        concept = retire_concept(
            db,
            concept_id=concept_id,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )
        return serialize_concept(concept)

    except (ConceptNotFound, ConceptConflict) as exc:
        raise service_error(exc) from exc


# ==========================================
# JINJA ADMIN INTERFACE
# ==========================================


@router.get("/admin/concepts", response_class=HTMLResponse, name="admin_concepts")
def admin_concepts_page(
    request: Request,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    page: int = Query(default=1, ge=1, le=10000),
    q: str | None = Query(default=None, max_length=200),
    kind: ConceptKind | None = None,
    concept_status: Annotated[
        ConceptStatus | None,
        Query(alias="status"),
    ] = None,
    notice: str | None = None,
):
    page_size = 20

    concepts, total = list_concepts(
        db,
        page=page,
        page_size=page_size,
        query=q,
        kind=kind,
        status=concept_status,
    )

    messages = {
        "created": "Medical concept created successfully.",
        "updated": "Medical concept updated successfully.",
        "retired": "Medical concept retired successfully.",
    }

    settings = request.app.state.settings

    context = {
        "page_title": "Medical Concepts",
        "active_page": "concepts",
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "admin_user": authenticated.user,
        "csrf_token": session_csrf_token(authenticated.session),
        "concepts": concepts,
        "q": q or "",
        "selected_kind": kind or "",
        "selected_status": concept_status or "",
        "page": page,
        "pages": max(1, math.ceil(total / page_size)),
        "total": total,
        "notice": messages.get(notice),
        "flash": None,
        "form_errors": (),
    }

    response = templates.TemplateResponse(
        request=request,
        name="admin/medical_concepts/concepts.html",
        context=context,
    )

    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


@router.post("/admin/concepts", name="admin_create_concept")
def admin_create_concept(
    request: Request,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    csrf_token: str = Form(...),
    kind: str = Form(...),
    namespace: str = Form("local"),
    canonical_name: str = Form(...),
    ontology_code: str = Form(""),
    concept_status: str = Form("draft"),
    aliases: str = Form(""),
):
    require_csrf(authenticated, csrf_token)

    try:
        data = parse_form(
            kind=kind,
            namespace=namespace,
            canonical_name=canonical_name,
            ontology_code=ontology_code,
            concept_status=concept_status,
            aliases=aliases,
        )

        create_concept(
            db,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

    except ValidationError:
        return form_error_response(request, "Invalid concept", 422)
    except (ConceptConflict, ConceptValidationError) as exc:
        return form_error_response(request, str(exc), 409)

    return RedirectResponse("/admin/concepts?notice=created", status_code=303)


@router.post("/admin/concepts/{concept_id}/update", name="admin_update_concept")
def admin_update_concept(
    request: Request,
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    csrf_token: str = Form(...),
    kind: str = Form(...),
    namespace: str = Form(...),
    canonical_name: str = Form(...),
    ontology_code: str = Form(""),
    concept_status: str = Form("draft"),
    aliases: str = Form(""),
):
    require_csrf(authenticated, csrf_token)

    try:
        data = parse_form(
            kind=kind,
            namespace=namespace,
            canonical_name=canonical_name,
            ontology_code=ontology_code,
            concept_status=concept_status,
            aliases=aliases,
        )

        update_concept(
            db,
            concept_id=concept_id,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

    except ValidationError:
        return form_error_response(request, "Invalid concept", 422)

    except (
        ConceptNotFound,
        ConceptConflict,
        ConceptValidationError,
    ) as exc:
        raise service_error(exc) from exc

    return RedirectResponse("/admin/concepts?notice=updated", status_code=303)


@router.post("/admin/concepts/{concept_id}/retire", name="admin_retire_concept")
def admin_retire_concept(
    request: Request,
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    csrf_token: str = Form(...),
):
    require_csrf(authenticated, csrf_token)

    try:
        retire_concept(
            db,
            concept_id=concept_id,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

    except (ConceptNotFound, ConceptConflict) as exc:
        raise service_error(exc) from exc

    return RedirectResponse("/admin/concepts?notice=retired", status_code=303)
