"""Phase 10 - Symptom admin endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import HTMLResponse

from app.api.admin.clinical_entities.common import render_clinical_page, service_error
from app.api.admin.concepts import require_csrf
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import DoctorAdminDependency
from app.schemas.clinical_entities import (
    ClinicalEntityStatus,
    ConceptOption,
    LifecycleAction,
    LifecycleRequest,
    SymptomCreate,
    SymptomList,
    SymptomRead,
    SymptomUpdate,
)
from app.services.admin.clinical_entities.common import (
    ClinicalEntityError,
    serialize_entity,
)
from app.services.admin.clinical_entities.symptom import (
    create_symptom,
    get_symptom,
    list_symptoms,
    review_symptom,
    search_symptom_concepts,
    update_symptom,
)

router = APIRouter(tags=["Symptoms"])


# ==========================================
# JINJA ADMIN PAGE
# ==========================================


@router.get(
    "/admin/symptoms",
    response_class=HTMLResponse,
    name="admin_symptoms",
)
def admin_symptoms_page(
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
    """Render the protected symptom management page."""

    return render_clinical_page(
        request,
        db,
        authenticated,
        kind="symptom",
        page=page,
        query=q,
        entity_status=entity_status,
    )


# ==========================================
# JSON API - LIST SYMPTOMS
# ==========================================


@router.get(
    "/api/admin/symptoms",
    response_model=SymptomList,
)
def api_list_symptoms(
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
    """Return paginated symptoms with optional filters."""

    items, total = list_symptoms(
        db,
        page=page,
        page_size=page_size,
        query=q,
        entity_status=entity_status,
    )

    return SymptomList(
        items=[serialize_entity(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# ==========================================
# JSON API - CONCEPT AUTOCOMPLETE
# ==========================================


@router.get(
    "/api/admin/symptoms/concept-options",
    response_model=list[ConceptOption],
)
def api_symptom_concept_options(
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    q: Annotated[
        str,
        Query(min_length=1, max_length=200),
    ],
):
    """Search available symptom medical concepts."""

    return search_symptom_concepts(
        db,
        q,
    )


# ==========================================
# JSON API - GET SYMPTOM
# ==========================================


@router.get(
    "/api/admin/symptoms/{concept_id}",
    response_model=SymptomRead,
)
def api_get_symptom(
    concept_id: uuid.UUID,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
):
    """Return a symptom by its medical concept ID."""

    try:
        entity = get_symptom(
            db,
            concept_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc


# ==========================================
# JSON API - CREATE SYMPTOM
# ==========================================


@router.post(
    "/api/admin/symptoms",
    response_model=SymptomRead,
    status_code=201,
)
def api_create_symptom(
    request: Request,
    data: SymptomCreate,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Create a new symptom draft."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = create_symptom(
            db,
            data=data,
            actor_id=authenticated.user.id,
            trace_id=request.state.trace_id,
        )

        return serialize_entity(entity)

    except ClinicalEntityError as exc:
        raise service_error(exc) from exc


# ==========================================
# JSON API - UPDATE SYMPTOM
# ==========================================


@router.put(
    "/api/admin/symptoms/{concept_id}",
    response_model=SymptomRead,
)
def api_update_symptom(
    request: Request,
    concept_id: uuid.UUID,
    data: SymptomUpdate,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Update an existing draft symptom."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = update_symptom(
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
# JSON API - SYMPTOM LIFECYCLE
# ==========================================


@router.post(
    "/api/admin/symptoms/{concept_id}/{action}",
    response_model=SymptomRead,
)
def api_review_symptom(
    request: Request,
    concept_id: uuid.UUID,
    action: LifecycleAction,
    data: LifecycleRequest,
    db: DatabaseSessionDependency,
    authenticated: DoctorAdminDependency,
    x_csrf_token: Annotated[str | None, Header()] = None,
):
    """Submit, approve, reject or retire a symptom."""

    require_csrf(
        authenticated,
        x_csrf_token,
    )

    try:
        entity = review_symptom(
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
