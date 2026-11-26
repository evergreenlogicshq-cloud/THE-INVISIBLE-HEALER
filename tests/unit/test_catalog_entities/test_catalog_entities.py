"""Phase 11 catalog validation, lifecycle, and database constraint tests.

All records are synthetic and use the isolated in-memory test database.
"""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.models.admin.medical_concepts.catalog_entities import Ingredient
from app.schemas.medical_concepts.catalog_entities.common import (
    IngredientCreate,
    IngredientUpdate,
    ProductCreate,
    ProductUpdate,
    RemedyCreate,
    RemedyUpdate,
)
from app.schemas.medical_concepts.clinical_entities.common import LifecycleRequest
from app.schemas.medical_concepts.concept import ConceptWrite
from app.services.admin.medical_concepts.clinical_entities.common import (
    ClinicalEntityConflict,
    ClinicalEntityNotFound,
    ClinicalEntityValidationError,
    create_entity,
    get_entity,
    list_entities,
    search_available_concepts,
    transition_entity,
    update_entity,
)
from app.services.admin.medical_concepts.concepts import create_concept, retire_concept

CASES = [
    ("product", ProductCreate, ProductUpdate),
    ("remedy", RemedyCreate, RemedyUpdate),
    ("ingredient", IngredientCreate, IngredientUpdate),
]


@pytest.fixture
def catalog_session(test_engine):
    Base.metadata.create_all(test_engine)
    try:
        with Session(test_engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(test_engine)


@pytest.fixture
def actor():
    return uuid.uuid4()


def make_concept(db, actor, kind, name, *, status="approved", aliases=None):
    return create_concept(
        db,
        data=ConceptWrite(
            kind=kind, canonical_name=name, status=status, aliases=aliases or []
        ),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )


def make_record(db, actor, kind, schema, concept_id, **fields):
    values = {
        "description": "Synthetic description",
        "source_reference": "Synthetic source",
        **fields,
    }
    return create_entity(
        db,
        kind=kind,
        data=schema(concept_id=concept_id, **values),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )


def change_status(db, actor, kind, concept_id, action, version, notes=None):
    return transition_entity(
        db,
        kind=kind,
        concept_id=concept_id,
        action=action,
        data=LifecycleRequest(version=version, notes=notes),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )


def event_count(db, kind):
    return db.scalar(
        select(func.count())
        .select_from(AuditEvent)
        .where(AuditEvent.resource_type == kind)
    )


@pytest.mark.parametrize(("kind", "create_schema", "update_schema"), CASES)
def test_draft_edit_requires_current_version(
    catalog_session, actor, kind, create_schema, update_schema
):
    db = catalog_session
    concept = make_concept(db, actor, kind, f"Versioned {kind}")
    record = make_record(db, actor, kind, create_schema, concept.id)
    assert (record.status, record.version) == ("draft", 1)
    saved = update_entity(
        db,
        kind=kind,
        concept_id=concept.id,
        data=update_schema(version=1, description="Updated", source_reference="Source"),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    assert (saved.description, saved.version) == ("Updated", 2)
    before = event_count(db, kind)
    with pytest.raises(ClinicalEntityConflict):
        update_entity(
            db,
            kind=kind,
            concept_id=concept.id,
            data=update_schema(version=1, description="Stale"),
            actor_id=actor,
            trace_id=str(uuid.uuid4()),
        )
    assert get_entity(db, kind=kind, concept_id=concept.id).description == "Updated"
    assert event_count(db, kind) == before


@pytest.mark.parametrize(("kind", "create_schema", "update_schema"), CASES)
def test_review_transitions_require_source_description_and_notes(
    catalog_session, actor, kind, create_schema, update_schema
):
    db = catalog_session
    concept = make_concept(db, actor, kind, f"Review {kind}")
    make_record(
        db,
        actor,
        kind,
        create_schema,
        concept.id,
        description="",
        source_reference=None,
    )
    with pytest.raises(ClinicalEntityValidationError):
        change_status(db, actor, kind, concept.id, "submit", 1)
    update_entity(
        db,
        kind=kind,
        concept_id=concept.id,
        data=update_schema(version=1, description="Description"),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    with pytest.raises(ClinicalEntityValidationError):
        change_status(db, actor, kind, concept.id, "submit", 2)
    update_entity(
        db,
        kind=kind,
        concept_id=concept.id,
        data=update_schema(
            version=2, description="Description", source_reference="Source"
        ),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    reviewed = change_status(db, actor, kind, concept.id, "submit", 3)
    assert (reviewed.status, reviewed.version) == ("in_review", 4)
    with pytest.raises(ClinicalEntityValidationError):
        change_status(db, actor, kind, concept.id, "reject", 4, notes="  ")
    returned = change_status(
        db, actor, kind, concept.id, "reject", 4, notes="Needs changes"
    )
    assert (returned.status, returned.review_notes, returned.version) == (
        "draft",
        "Needs changes",
        5,
    )
    updated = update_entity(
        db,
        kind=kind,
        concept_id=concept.id,
        data=update_schema(version=5, description="Revised", source_reference="Source"),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    assert updated.review_notes is None and updated.reviewed_by is None


@pytest.mark.parametrize(("kind", "create_schema", "update_schema"), CASES)
def test_creation_rejects_missing_wrong_retired_and_duplicate_concepts(
    catalog_session, actor, kind, create_schema, update_schema
):
    db = catalog_session
    with pytest.raises(ClinicalEntityNotFound):
        make_record(db, actor, kind, create_schema, uuid.uuid4())
    other_kind = "remedy" if kind == "product" else "product"
    other = make_concept(db, actor, other_kind, f"Wrong parent for {kind}")
    with pytest.raises(ClinicalEntityValidationError):
        make_record(db, actor, kind, create_schema, other.id)
    retired = make_concept(db, actor, kind, f"Retired {kind}")
    retire_concept(
        db, concept_id=retired.id, actor_id=actor, trace_id=str(uuid.uuid4())
    )
    with pytest.raises(ClinicalEntityConflict):
        make_record(db, actor, kind, create_schema, retired.id)
    concept = make_concept(db, actor, kind, f"Existing {kind}")
    make_record(db, actor, kind, create_schema, concept.id)
    with pytest.raises(ClinicalEntityConflict):
        make_record(db, actor, kind, create_schema, concept.id)
    assert event_count(db, kind) == 1


@pytest.mark.parametrize(("kind", "create_schema", "update_schema"), CASES)
def test_retirement_is_soft_and_terminal(
    catalog_session, actor, kind, create_schema, update_schema
):
    db = catalog_session
    concept = make_concept(db, actor, kind, f"Retire {kind}")
    make_record(db, actor, kind, create_schema, concept.id)
    record = change_status(db, actor, kind, concept.id, "retire", 1)
    assert record.status == "retired" and record.retired_at is not None
    assert get_entity(db, kind=kind, concept_id=concept.id).version == 2
    with pytest.raises(ClinicalEntityConflict):
        change_status(db, actor, kind, concept.id, "submit", 2)
    with pytest.raises(ClinicalEntityConflict):
        update_entity(
            db,
            kind=kind,
            concept_id=concept.id,
            data=update_schema(version=2),
            actor_id=actor,
            trace_id=str(uuid.uuid4()),
        )
    assert [
        item.status for item in list_entities(db, kind=kind, entity_status="retired")[0]
    ] == ["retired"]


@pytest.mark.parametrize(("kind", "create_schema", "update_schema"), CASES)
def test_search_includes_aliases_and_excludes_used_concepts(
    catalog_session, actor, kind, create_schema, update_schema
):
    db = catalog_session
    concept = make_concept(
        db, actor, kind, f"Search {kind}", aliases=[f"Alternate {kind}"]
    )
    options = search_available_concepts(db, kind=kind, query="alternate")
    assert [option.id for option in options] == [concept.id]
    make_record(db, actor, kind, create_schema, concept.id)
    assert search_available_concepts(db, kind=kind, query="alternate") == []
    records, total = list_entities(db, kind=kind, query="alternate")
    assert total == 1 and records[0].concept_id == concept.id


@pytest.mark.parametrize(
    "amount", ["0", "-1", "NaN", "Infinity", "1.0000001", "1000000000000"]
)
def test_ingredient_rejects_invalid_reference_amounts(amount):
    with pytest.raises(ValidationError):
        IngredientCreate(
            concept_id=uuid.uuid4(),
            source_reference="Source",
            reference_amount=amount,
            reference_unit="mg",
            reference_basis="per serving",
        )


def test_ingredient_accepts_precise_documented_reference_amount():
    ingredient = IngredientCreate(
        concept_id=uuid.uuid4(),
        source_reference="Source",
        reference_amount="0.000001",
        reference_unit="mg",
        reference_basis="per serving",
    )
    assert ingredient.reference_amount == Decimal("0.000001")


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {
            "reference_amount": Decimal(0),
            "reference_unit": "mg",
            "reference_basis": "serving",
        },
        {
            "reference_amount": Decimal(1),
            "reference_unit": None,
            "reference_basis": "serving",
        },
        {"status": "unknown"},
        {"version": 0},
    ],
)
def test_database_enforces_catalog_constraints(catalog_session, actor, invalid_fields):
    db = catalog_session
    concept = make_concept(db, actor, "ingredient", "Constraint ingredient")
    make_record(db, actor, "ingredient", IngredientCreate, concept.id)
    ingredient = db.get(Ingredient, concept.id)
    for field, value in invalid_fields.items():
        setattr(ingredient, field, value)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    ingredient = db.get(Ingredient, concept.id)
    assert ingredient.status == "draft" and ingredient.version == 1
    assert ingredient.reference_amount is None
