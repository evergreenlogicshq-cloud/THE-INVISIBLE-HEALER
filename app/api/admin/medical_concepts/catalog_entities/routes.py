"""Protected product, remedy and ingredient management endpoints."""

import math
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from app.api.admin.dashboard import templates
from app.api.admin.medical_concepts.clinical_entities.common import service_error
from app.api.admin.medical_concepts.concepts import require_csrf
from app.api.dependencies import DatabaseSessionDependency
from app.core.permissions import DoctorAdminDependency
from app.schemas.medical_concepts.catalog_entities.common import (
    CatalogList,
    IngredientCreate,
    IngredientRead,
    IngredientUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    RemedyCreate,
    RemedyRead,
    RemedyUpdate,
)
from app.schemas.medical_concepts.clinical_entities.common import (
    ConceptOption,
    LifecycleAction,
    LifecycleRequest,
)
from app.services.admin.auth import session_csrf_token
from app.services.admin.medical_concepts.clinical_entities.common import (
    ClinicalEntityError,
    create_entity,
    get_entity,
    list_entities,
    search_available_concepts,
    serialize_entity,
    transition_entity,
    update_entity,
)

CATALOG_SECTIONS = {
    "products": (
        "product",
        "Products",
        ProductCreate,
        ProductUpdate,
        [
            ("manufacturer", "Manufacturer"),
            ("brand", "Brand"),
            ("dosage_form", "Dosage Form"),
            ("product_category", "Product Category"),
            ("country_of_origin", "Country of Origin"),
            ("regulatory_number", "Regulatory Number"),
        ],
    ),
    "remedies": (
        "remedy",
        "Remedies",
        RemedyCreate,
        RemedyUpdate,
        [
            ("remedy_type", "Remedy Type"),
            ("preparation", "Preparation"),
            ("administration_route", "Administration Route"),
            ("limitations", "Limitations"),
        ],
    ),
    "ingredients": (
        "ingredient",
        "Ingredients",
        IngredientCreate,
        IngredientUpdate,
        [
            ("scientific_name", "Scientific Name"),
            ("ingredient_type", "Ingredient Type"),
            ("source_part", "Source Part"),
            ("reference_amount", "Reference Amount"),
            ("reference_unit", "Reference Unit"),
            ("reference_basis", "Reference Basis"),
        ],
    ),
}
StatusFilter = Literal["", "draft", "in_review", "approved", "retired"]


def validate_payload(schema, payload):
    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail=exc.errors(include_context=False, include_url=False)
        ) from exc


def build_catalog_router(section):
    kind, title, create_schema, update_schema, fields = CATALOG_SECTIONS[section]
    read_schema = {
        "product": ProductRead,
        "remedy": RemedyRead,
        "ingredient": IngredientRead,
    }[kind]
    sub = APIRouter(tags=[title])
    base = f"/api/admin/{section}"

    @sub.get(f"/admin/{section}", response_class=HTMLResponse, name=f"admin_{section}")
    def page_view(
        request: Request,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        page: Annotated[int, Query(ge=1, le=10000)] = 1,
        q: Annotated[str | None, Query(max_length=200)] = None,
        entity_status: Annotated[StatusFilter | None, Query(alias="status")] = None,
    ):
        items, total = list_entities(
            db, kind=kind, page=page, page_size=20, query=q, entity_status=entity_status
        )
        settings = request.app.state.settings
        response = templates.TemplateResponse(
            request=request,
            name="admin/medical_concepts/catalog_entities/catalog.html",
            context={
                "page_title": title,
                "active_page": section,
                "section": section,
                "kind": kind,
                "fields": fields,
                "app_name": settings.APP_NAME,
                "app_version": settings.APP_VERSION,
                "environment": settings.APP_ENV,
                "admin_user": authenticated.user,
                "csrf_token": session_csrf_token(authenticated.session),
                "entities": [serialize_entity(x) for x in items],
                "q": q or "",
                "selected_status": entity_status or "",
                "page": page,
                "pages": max(1, math.ceil(total / 20)),
                "total": total,
                "flash": None,
                "form_errors": (),
            },
        )
        response.headers.update(
            {
                "Cache-Control": "no-store, private",
                "Pragma": "no-cache",
                "X-Content-Type-Options": "nosniff",
            }
        )
        return response

    @sub.get(base, response_model=CatalogList, name=f"list_{section}")
    def list_view(
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        page: Annotated[int, Query(ge=1, le=10000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
        q: Annotated[str | None, Query(max_length=200)] = None,
        entity_status: Annotated[StatusFilter | None, Query(alias="status")] = None,
    ):
        items, total = list_entities(
            db,
            kind=kind,
            page=page,
            page_size=page_size,
            query=q,
            entity_status=entity_status,
        )
        return CatalogList(
            items=[serialize_entity(x) for x in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    @sub.get(
        base + "/concept-options",
        response_model=list[ConceptOption],
        name=f"options_{section}",
    )
    def options(
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        q: Annotated[str, Query(min_length=1, max_length=200)],
    ):
        return search_available_concepts(db, kind=kind, query=q)

    @sub.get(base + "/{concept_id}", response_model=read_schema, name=f"get_{section}")
    def get_record(
        concept_id: uuid.UUID,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
    ):
        try:
            return serialize_entity(get_entity(db, kind=kind, concept_id=concept_id))
        except ClinicalEntityError as exc:
            raise service_error(exc) from exc

    @sub.post(
        base, response_model=read_schema, status_code=201, name=f"create_{section}"
    )
    def create(
        request: Request,
        payload: dict,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
    ):
        require_csrf(authenticated, x_csrf_token)
        data = validate_payload(create_schema, payload)
        try:
            return serialize_entity(
                create_entity(
                    db,
                    kind=kind,
                    data=data,
                    actor_id=authenticated.user.id,
                    trace_id=request.state.trace_id,
                )
            )
        except ClinicalEntityError as exc:
            raise service_error(exc) from exc

    @sub.put(
        base + "/{concept_id}", response_model=read_schema, name=f"update_{section}"
    )
    def update(
        request: Request,
        concept_id: uuid.UUID,
        payload: dict,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
    ):
        require_csrf(authenticated, x_csrf_token)
        data = validate_payload(update_schema, payload)
        try:
            return serialize_entity(
                update_entity(
                    db,
                    kind=kind,
                    concept_id=concept_id,
                    data=data,
                    actor_id=authenticated.user.id,
                    trace_id=request.state.trace_id,
                )
            )
        except ClinicalEntityError as exc:
            raise service_error(exc) from exc

    @sub.post(
        base + "/{concept_id}/{action}",
        response_model=read_schema,
        name=f"review_{section}",
    )
    def review(
        request: Request,
        concept_id: uuid.UUID,
        action: LifecycleAction,
        data: LifecycleRequest,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        x_csrf_token: Annotated[str | None, Header()] = None,
    ):
        require_csrf(authenticated, x_csrf_token)
        try:
            return serialize_entity(
                transition_entity(
                    db,
                    kind=kind,
                    concept_id=concept_id,
                    action=action,
                    data=data,
                    actor_id=authenticated.user.id,
                    trace_id=request.state.trace_id,
                )
            )
        except ClinicalEntityError as exc:
            raise service_error(exc) from exc

    @sub.delete(
        base + "/{concept_id}", response_model=read_schema, name=f"delete_{section}"
    )
    def retire(
        request: Request,
        concept_id: uuid.UUID,
        db: DatabaseSessionDependency,
        authenticated: DoctorAdminDependency,
        version: Annotated[int, Query(ge=1)],
        x_csrf_token: Annotated[str | None, Header()] = None,
    ):
        require_csrf(authenticated, x_csrf_token)
        try:
            return serialize_entity(
                transition_entity(
                    db,
                    kind=kind,
                    concept_id=concept_id,
                    action="retire",
                    data=LifecycleRequest(version=version),
                    actor_id=authenticated.user.id,
                    trace_id=request.state.trace_id,
                )
            )
        except ClinicalEntityError as exc:
            raise service_error(exc) from exc

    return sub


router = APIRouter()
for section in CATALOG_SECTIONS:
    router.include_router(build_catalog_router(section))
