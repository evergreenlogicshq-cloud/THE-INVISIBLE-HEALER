"""Phase 10 - Health issue service interface."""

import uuid

from sqlalchemy.orm import Session

from app.models.admin.clinical_entities import HealthIssue
from app.schemas.clinical_entities import (
    HealthIssueCreate,
    HealthIssueUpdate,
    LifecycleAction,
    LifecycleRequest,
)
from app.services.admin.clinical_entities.common import (
    create_entity,
    get_entity,
    list_approved_entities,
    list_entities,
    search_available_concepts,
    transition_entity,
    update_entity,
)


def create_health_issue(
    db: Session,
    *,
    data: HealthIssueCreate,
    actor_id: uuid.UUID,
    trace_id: str,
) -> HealthIssue:
    return create_entity(
        db,
        kind="health_issue",
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def get_health_issue(db: Session, concept_id: uuid.UUID) -> HealthIssue:
    return get_entity(db, kind="health_issue", concept_id=concept_id)


def list_health_issues(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    query: str | None = None,
    entity_status: str | None = None,
):
    return list_entities(
        db,
        kind="health_issue",
        page=page,
        page_size=page_size,
        query=query,
        entity_status=entity_status,
    )


def update_health_issue(
    db: Session,
    *,
    concept_id: uuid.UUID,
    data: HealthIssueUpdate,
    actor_id: uuid.UUID,
    trace_id: str,
) -> HealthIssue:
    return update_entity(
        db,
        kind="health_issue",
        concept_id=concept_id,
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def review_health_issue(
    db: Session,
    *,
    concept_id: uuid.UUID,
    action: LifecycleAction,
    data: LifecycleRequest,
    actor_id: uuid.UUID,
    trace_id: str,
) -> HealthIssue:
    return transition_entity(
        db,
        kind="health_issue",
        concept_id=concept_id,
        action=action,
        data=data,
        actor_id=actor_id,
        trace_id=trace_id,
    )


def search_health_issue_concepts(db: Session, query: str):
    return search_available_concepts(db, kind="health_issue", query=query)


def get_approved_health_issues(db: Session):
    return list_approved_entities(db, kind="health_issue")
