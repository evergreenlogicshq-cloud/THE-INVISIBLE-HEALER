"""Phase 10 - Symptom service interface."""

import uuid

from sqlalchemy.orm import Session

from app.models.admin.medical_concepts.clinical_entities import Symptom
from app.schemas.medical_concepts.clinical_entities import (
    LifecycleAction,
    LifecycleRequest,
    SymptomCreate,
    SymptomUpdate,
)
from app.services.admin.medical_concepts.clinical_entities.common import (
    create_entity,
    get_entity,
    list_approved_entities,
    list_entities,
    search_available_concepts,
    transition_entity,
    update_entity,
)


def create_symptom(
    db: Session,
    *,
    data: SymptomCreate,
    actor_id: uuid.UUID,
    trace_id: str,
) -> Symptom:
    return create_entity(
        db,
        kind="symptom",
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def get_symptom(db: Session, concept_id: uuid.UUID) -> Symptom:
    return get_entity(db, kind="symptom", concept_id=concept_id)


def list_symptoms(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    query: str | None = None,
    entity_status: str | None = None,
):
    return list_entities(
        db,
        kind="symptom",
        page=page,
        page_size=page_size,
        query=query,
        entity_status=entity_status,
    )


def update_symptom(
    db: Session,
    *,
    concept_id: uuid.UUID,
    data: SymptomUpdate,
    actor_id: uuid.UUID,
    trace_id: str,
) -> Symptom:
    return update_entity(
        db,
        kind="symptom",
        concept_id=concept_id,
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def review_symptom(
    db: Session,
    *,
    concept_id: uuid.UUID,
    action: LifecycleAction,
    data: LifecycleRequest,
    actor_id: uuid.UUID,
    trace_id: str,
) -> Symptom:
    return transition_entity(
        db,
        kind="symptom",
        concept_id=concept_id,
        action=action,
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def search_symptom_concepts(db: Session, query: str):
    return search_available_concepts(db, kind="symptom", query=query)


def get_approved_symptoms(db: Session):
    return list_approved_entities(db, kind="symptom")
