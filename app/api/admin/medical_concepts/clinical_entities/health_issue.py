"""Phase 10 - Health issue admin endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import HTMLResponse

from app.api.admin.medical_concepts.clinical_entities.common import (
    render_clinical_page,
    service_error,
)
from app.api.admin.medical_concepts.concepts import require_csrf
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import DoctorAdminDependency
from app.schemas.medical_concepts.clinical_entities import (
    ClinicalEntityStatus,
    ConceptOption,
    HealthIssueCreate,
    HealthIssueList,
    HealthIssueRead,
    HealthIssueUpdate,
    LifecycleAction,
    LifecycleRequest,
)
from app.services.admin.medical_concepts.clinical_entities.common import (
    ClinicalEntityError,
    serialize_entity,
)
from app.services.admin.medical_concepts.clinical_entities.health_issue import (
    create_health_issue,
    get_health_issue,
    list_health_issues,
    review_health_issue,
    search_health_issue_concepts,
    update_health_issue,
)

router = APIRouter(tags=["Health Issues"])


# ==========================================
# JINJA ADMIN PAGE
# ==========================================


@router.get(
    "/admin/health-issues", response_class=HTMLResponse, name="admin_health_issues"
)
def admin_health_issues_page(
    request: Request,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    q: Annotated[str | None, Query(max_length=200)] = None,
    entity_status: Annotated[
        ClinicalEntityStatus | None,
        Query(alias="status"),
    ] = None,
):
    """Render the protected health issue management page."""

    return render_clinical_page(
        request,
        db,
        authenticated,
        kind="health_issue",
        page=page,
        query=q,
        entity_status=entity_status,
    )


# ==========================================
# JSON API - LIST HEALTH ISSUES
# ==========================================


@router.get("/api/admin/health-issues", response_model=HealthIssueList)
def api_list_health_issues(
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
    entity_status: Annotated[
        ClinicalEntityStatus | None,
        Query(alias="status"),
    ] = None,
):
    """Return paginated health issues with optional filters."""

    items, total = list_health_issues(
        db,
        page=page,
        page_size=page_size,
        query=q,
        entity_status=entity_status,
    )

    return HealthIssueList(
        items=[serialize_entity(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==========================================
# JSON API - CONCEPT AUTOCOMPLETE
# ==========================================


@router.get(
    "/api/admin/health-issues/concept-options", response_model=list[ConceptOption]
)
def api_health_issue_concept_options(
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    q: Annotated[
        str,
        Query(min_length=1, max_length=200),
    ],
):
    """Search available health issue medical concepts."""

    return search_health_issue_concepts(db, q)


# ==========================================
# JSON API - GET HEALTH ISSUE
# ==========================================


@router.get("/api/admin/health-issues/{concept_id}", response_model=HealthIssueRead)
def api_get_health_issue(
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
):
    """Return a health issue by its medical concept ID."""

    try:
        entity = get_health_issue(
            db,
            concept_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc


# ==========================================
# JSON API - CREATE HEALTH ISSUE
# ==========================================


@router.post(
    "/api/admin/health-issues",
    response_model=HealthIssueRead,
    status_code=201,
)
def api_create_health_issue(
    request: Request,
    data: HealthIssueCreate,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Create a new health issue draft."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = create_health_issue(
            db,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc


# ==========================================
# JSON API - UPDATE HEALTH ISSUE
# ==========================================


@router.put(
    "/api/admin/health-issues/{concept_id}",
    response_model=HealthIssueRead,
)
def api_update_health_issue(
    request: Request,
    concept_id: uuid.UUID,
    data: HealthIssueUpdate,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Update an existing draft health issue."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = update_health_issue(
            db,
            concept_id=concept_id,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc


# ==========================================
# JSON API - HEALTH ISSUE LIFECYCLE
# ==========================================


@router.post(
    "/api/admin/health-issues/{concept_id}/{action}",
    response_model=HealthIssueRead,
)
def api_review_health_issue(
    request: Request,
    concept_id: uuid.UUID,
    action: LifecycleAction,
    data: LifecycleRequest,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Submit, approve, reject or retire a health issue."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = review_health_issue(
            db,
            concept_id=concept_id,
            action=action,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc
