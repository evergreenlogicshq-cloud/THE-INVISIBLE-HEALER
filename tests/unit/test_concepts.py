"""Phase 09 - Medical concept unit tests."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.models.admin.concept import MedicalConcept
from app.schemas.concept import ConceptWrite, normalize_label
from app.services.admin.concepts import (
    ConceptConflict,
    ConceptValidationError,
    create_concept,
    get_concept,
    resolve_concept,
    retire_concept,
    update_concept,
)


@pytest.fixture
def concept_db(test_engine):
    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(test_engine)


@pytest.fixture
def actor_id():
    return uuid.uuid4()


@pytest.fixture
def trace_id():
    return str(uuid.uuid4())


def payload(name="Headache", aliases=None, kind="symptom"):
    return ConceptWrite(
        kind=kind,
        namespace="local",
        canonical_name=name,
        aliases=aliases or [],
        status="draft",
    )


def test_normalization():
    assert normalize_label("  FEVER  ") == "fever"
    assert normalize_label("High   Fever") == "high fever"
    assert normalize_label("Ｆｅｖｅｒ") == "fever"


def test_create_concept(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload(
            "Headache",
            ["Head Pain", "Cephalalgia"],
        ),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    assert isinstance(concept.id, uuid.UUID)
    assert concept.normalized_name == "headache"
    assert concept.kind == "symptom"
    assert concept.status == "draft"
    assert len(concept.aliases) == 3
    assert sum(a.is_primary for a in concept.aliases) == 1


def test_duplicate_canonical_is_rejected(concept_db, actor_id, trace_id):
    create_concept(
        concept_db,
        data=payload("Fever"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptConflict):
        create_concept(
            concept_db,
            data=payload("  FEVER  "),
            actor_id=actor_id,
            trace_id=trace_id,
        )


def test_alias_cannot_collide_with_canonical(concept_db, actor_id, trace_id):
    create_concept(
        concept_db,
        data=payload("Headache", ["Head Pain"]),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptConflict):
        create_concept(
            concept_db,
            data=payload("Head Pain"),
            actor_id=actor_id,
            trace_id=trace_id,
        )


def test_alias_collision_is_rejected(concept_db, actor_id, trace_id):
    create_concept(
        concept_db,
        data=payload("Headache", ["Cephalalgia"]),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptConflict):
        create_concept(
            concept_db,
            data=payload("Migraine", ["CEPHALALGIA"]),
            actor_id=actor_id,
            trace_id=trace_id,
        )


def test_different_namespaces_are_independent(concept_db, actor_id, trace_id):
    first = create_concept(
        concept_db,
        data=payload("Pain"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    second_data = payload("Pain")
    second_data.namespace = "external"

    second = create_concept(
        concept_db,
        data=second_data,
        actor_id=actor_id,
        trace_id=trace_id,
    )

    assert first.id != second.id


def test_alias_resolution(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Headache", ["Head Pain"]),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    found = resolve_concept(concept_db, term="HEAD PAIN")

    assert found is not None
    assert found.id == concept.id


def test_update_preserves_uuid(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Headache"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    updated = update_concept(
        concept_db,
        concept_id=concept.id,
        data=payload("Headache Disorder", ["Head Pain"]),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    assert updated.id == concept.id
    assert updated.canonical_name == "Headache Disorder"
    assert len(updated.aliases) == 2


def test_kind_cannot_change(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Fever"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptValidationError):
        update_concept(
            concept_db,
            concept_id=concept.id,
            data=payload("Fever", kind="health_issue"),
            actor_id=actor_id,
            trace_id=trace_id,
        )


def test_retirement_preserves_record(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Headache"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    retired = retire_concept(
        concept_db,
        concept_id=concept.id,
        actor_id=actor_id,
        trace_id=trace_id,
    )

    assert retired.status == "retired"
    assert retired.retired_at is not None

    persisted = get_concept(concept_db, concept.id)
    assert persisted.id == concept.id

    assert resolve_concept(concept_db, term="Headache") is None


def test_retired_concept_cannot_be_edited(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Fever"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    retire_concept(
        concept_db,
        concept_id=concept.id,
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptValidationError):
        update_concept(
            concept_db,
            concept_id=concept.id,
            data=payload("New Fever"),
            actor_id=actor_id,
            trace_id=trace_id,
        )


def test_concept_creates_attributable_audit(concept_db, actor_id, trace_id):
    concept = create_concept(
        concept_db,
        data=payload("Fever"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    event = concept_db.scalar(
        select(AuditEvent).where(AuditEvent.action == "medical_concept.create")
    )

    assert event is not None
    assert event.actor_id == actor_id
    assert event.resource_id == str(concept.id)
    assert event.trace_id == trace_id


def test_duplicate_failure_does_not_add_concept(concept_db, actor_id, trace_id):
    create_concept(
        concept_db,
        data=payload("Fever"),
        actor_id=actor_id,
        trace_id=trace_id,
    )

    with pytest.raises(ConceptConflict):
        create_concept(
            concept_db,
            data=payload("FEVER"),
            actor_id=actor_id,
            trace_id=trace_id,
        )

    assert len(concept_db.scalars(select(MedicalConcept)).all()) == 1
