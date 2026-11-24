"""Phase 10 - Clinical entity service tests."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.schemas.medical_concepts.clinical_entities import (
    HealthIssueCreate,
    HealthIssueUpdate,
    LifecycleRequest,
    SymptomCreate,
)
from app.schemas.medical_concepts.concept import ConceptWrite
from app.services.admin.medical_concepts.clinical_entities.common import (
    ClinicalEntityConflict,
    ClinicalEntityNotFound,
    ClinicalEntityValidationError,
)
from app.services.admin.medical_concepts.clinical_entities.health_issue import (
    create_health_issue,
    get_approved_health_issues,
    review_health_issue,
    search_health_issue_concepts,
    update_health_issue,
)
from app.services.admin.medical_concepts.clinical_entities.symptom import create_symptom
from app.services.admin.medical_concepts.concepts import (
    ConceptConflict,
    ConceptValidationError,
    create_concept,
    retire_concept,
    update_concept,
)


@pytest.fixture
def clinical_db(test_engine):
    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as db:
            yield db

    finally:
        Base.metadata.drop_all(test_engine)


@pytest.fixture
def actor_id():
    return uuid.uuid4()


def trace_id():
    return str(uuid.uuid4())


def make_concept(
    db,
    actor_id,
    *,
    kind="health_issue",
    name="Example Health Issue",
    status="approved",
    aliases=None,
):
    return create_concept(
        db,
        data=ConceptWrite(
            kind=kind,
            canonical_name=name,
            status=status,
            aliases=aliases or [],
        ),
        actor_id=actor_id,
        trace_id=trace_id(),
    )


def make_health_issue(db, actor_id, concept):
    return create_health_issue(
        db,
        data=HealthIssueCreate(
            concept_id=concept.id,
            description="Synthetic test record.",
            body_system="Example system",
        ),
        actor_id=actor_id,
        trace_id=trace_id(),
    )


def transition(
    db,
    actor_id,
    entity,
    action,
    notes=None,
):
    return review_health_issue(
        db,
        concept_id=entity.concept_id,
        action=action,
        data=LifecycleRequest(
            version=entity.version,
            notes=notes,
        ),
        actor_id=actor_id,
        trace_id=trace_id(),
    )


def test_create_health_issue(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    assert entity.concept_id == concept.id
    assert entity.status == "draft"
    assert entity.version == 1


def test_duplicate_health_issue(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    make_health_issue(clinical_db, actor_id, concept)

    with pytest.raises(ClinicalEntityConflict):
        make_health_issue(clinical_db, actor_id, concept)


def test_create_symptom(clinical_db, actor_id):
    concept = make_concept(
        clinical_db,
        actor_id,
        kind="symptom",
        name="Example Symptom",
    )

    symptom = create_symptom(
        clinical_db,
        data=SymptomCreate(
            concept_id=concept.id,
            description="Example symptom description.",
            body_location="Head",
            observation_type="subjective",
        ),
        actor_id=actor_id,
        trace_id=trace_id(),
    )

    assert symptom.concept_id == concept.id
    assert symptom.body_location == "Head"
    assert symptom.status == "draft"


def test_wrong_concept_kind(clinical_db, actor_id):
    concept = make_concept(
        clinical_db,
        actor_id,
        kind="symptom",
        name="Example Symptom",
    )

    with pytest.raises(ClinicalEntityValidationError):
        make_health_issue(clinical_db, actor_id, concept)


def test_missing_concept(clinical_db, actor_id):
    with pytest.raises(ClinicalEntityNotFound):
        create_health_issue(
            clinical_db,
            data=HealthIssueCreate(
                concept_id=uuid.uuid4(),
            ),
            actor_id=actor_id,
            trace_id=trace_id(),
        )


def test_invalid_classification():
    with pytest.raises(ValidationError):
        HealthIssueCreate(concept_id=uuid.uuid4(), typical_course="invalid")


def test_direct_approval_payload_rejected():
    with pytest.raises(ValidationError):
        HealthIssueCreate(concept_id=uuid.uuid4(), status="approved")


def test_review_lifecycle(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    entity = transition(clinical_db, actor_id, entity, "submit")

    assert entity.status == "in_review"

    entity = transition(
        clinical_db,
        actor_id,
        entity,
        "approve",
        notes="Synthetic review.",
    )

    assert entity.status == "approved"
    assert entity.version == 3
    assert entity.reviewed_by == actor_id
    assert entity.reviewed_at is not None


def test_draft_cannot_be_approved_directly(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)

    with pytest.raises(ClinicalEntityConflict):
        transition(
            clinical_db,
            actor_id,
            entity,
            "approve",
            notes="Invalid transition.",
        )


def test_unapproved_concept_blocks_approval(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id, status="draft")
    entity = make_health_issue(clinical_db, actor_id, concept)
    entity = transition(clinical_db, actor_id, entity, "submit")

    with pytest.raises(ClinicalEntityConflict):
        transition(
            clinical_db,
            actor_id,
            entity,
            "approve",
            notes="Test review.",
        )


def test_stale_update_rejected(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    update_health_issue(
        clinical_db,
        concept_id=entity.concept_id,
        data=HealthIssueUpdate(
            version=1,
            description="First update.",
        ),
        actor_id=actor_id,
        trace_id=trace_id(),
    )

    with pytest.raises(ClinicalEntityConflict):
        update_health_issue(
            clinical_db,
            concept_id=entity.concept_id,
            data=HealthIssueUpdate(
                version=1,
                description="Stale update.",
            ),
            actor_id=actor_id,
            trace_id=trace_id(),
        )


def test_approved_record_cannot_be_edited(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    entity = transition(clinical_db, actor_id, entity, "submit")
    entity = transition(
        clinical_db,
        actor_id,
        entity,
        "approve",
        notes="Synthetic review.",
    )

    with pytest.raises(ClinicalEntityConflict):
        update_health_issue(
            clinical_db,
            concept_id=entity.concept_id,
            data=HealthIssueUpdate(
                version=entity.version,
                description="Unauthorized modification.",
            ),
            actor_id=actor_id,
            trace_id=trace_id(),
        )


def test_rejection_returns_record_to_draft(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    entity = transition(clinical_db, actor_id, entity, "submit")
    entity = transition(
        clinical_db,
        actor_id,
        entity,
        "reject",
        notes="Further review required.",
    )

    assert entity.status == "draft"
    assert entity.review_notes is not None


def test_linked_concept_rename_blocked(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    make_health_issue(clinical_db, actor_id, concept)

    with pytest.raises(ConceptValidationError):
        update_concept(
            clinical_db,
            concept_id=concept.id,
            data=ConceptWrite(
                kind="health_issue",
                canonical_name="Changed Label",
                status="approved",
            ),
            actor_id=actor_id,
            trace_id=trace_id(),
        )


def test_linked_concept_retirement_blocked(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    make_health_issue(clinical_db, actor_id, concept)

    with pytest.raises(ConceptConflict):
        retire_concept(
            clinical_db,
            concept_id=concept.id,
            actor_id=actor_id,
            trace_id=trace_id(),
        )


def test_autocomplete_searches_aliases(
    clinical_db,
    actor_id,
):
    concept = make_concept(
        clinical_db,
        actor_id,
        name="Example Health Issue",
        aliases=["Alternative Name"],
    )

    results = search_health_issue_concepts(
        clinical_db,
        "alternative",
    )

    assert len(results) == 1
    assert results[0].id == concept.id

    make_health_issue(
        clinical_db,
        actor_id,
        concept,
    )

    assert (
        search_health_issue_concepts(
            clinical_db,
            "alternative",
        )
        == []
    )


def test_retired_entity_excluded(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)
    entity = transition(clinical_db, actor_id, entity, "submit")
    entity = transition(
        clinical_db,
        actor_id,
        entity,
        "approve",
        notes="Synthetic review.",
    )

    assert len(get_approved_health_issues(clinical_db)) == 1

    entity = transition(
        clinical_db,
        actor_id,
        entity,
        "retire",
    )

    assert entity.status == "retired"
    assert entity.retired_at is not None
    assert get_approved_health_issues(clinical_db) == []


def test_create_audit_event(clinical_db, actor_id):
    concept = make_concept(clinical_db, actor_id)
    entity = make_health_issue(clinical_db, actor_id, concept)

    event = clinical_db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "health_issue.create",
            AuditEvent.resource_id == str(entity.concept_id),
        )
    )

    assert event is not None
    assert event.actor_id == actor_id
    assert event.decision == "allowed"
    assert event.resource_version == "1"


def test_audit_failure_rolls_back_creation(clinical_db, actor_id, monkeypatch):
    concept = make_concept(clinical_db, actor_id)

    concept_id = concept.id

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Simulated audit failure.")

    monkeypatch.setattr(
        "app.services.admin.medical_concepts.clinical_entities.common.record_audit_event",
        fail_audit,
    )

    with pytest.raises(RuntimeError):
        make_health_issue(clinical_db, actor_id, concept)

    from app.models.admin.medical_concepts.clinical_entities import HealthIssue

    assert clinical_db.get(HealthIssue, concept_id) is None
