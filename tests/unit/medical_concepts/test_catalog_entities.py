"""Catalog eligibility, validation and transactional audit tests."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.models.admin.medical_concepts.catalog_entities import Product
from app.schemas.medical_concepts.catalog_entities.common import (
    IngredientCreate,
    ProductCreate,
    ProductUpdate,
    RemedyCreate,
)
from app.schemas.medical_concepts.clinical_entities.common import LifecycleRequest
from app.schemas.medical_concepts.concept import ConceptWrite
from app.services.admin.medical_concepts.catalog_entities.common import (
    get_approved_ingredients,
    get_approved_products,
    get_approved_remedies,
)
from app.services.admin.medical_concepts.clinical_entities.common import (
    create_entity,
    transition_entity,
    update_entity,
)
from app.services.admin.medical_concepts.concepts import create_concept


@pytest.fixture
def catalog_db(test_engine):
    Base.metadata.create_all(test_engine)
    try:
        with Session(test_engine) as db:
            yield db
    finally:
        Base.metadata.drop_all(test_engine)


@pytest.mark.parametrize(
    ("kind", "schema", "get_approved"),
    [
        ("product", ProductCreate, get_approved_products),
        ("remedy", RemedyCreate, get_approved_remedies),
        ("ingredient", IngredientCreate, get_approved_ingredients),
    ],
)
def test_approved_catalog_requires_approved_parent(
    catalog_db, kind, schema, get_approved
):
    db = catalog_db
    actor = uuid.uuid4()
    concept = create_concept(
        db,
        data=ConceptWrite(kind=kind, canonical_name="Synthetic", status="approved"),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    create_entity(
        db,
        kind=kind,
        data=schema(
            concept_id=concept.id, description="Example", source_reference="Source"
        ),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    assert get_approved(db) == []
    for action, version in (("submit", 1), ("approve", 2)):
        transition_entity(
            db,
            kind=kind,
            concept_id=concept.id,
            action=action,
            data=LifecycleRequest(version=version, notes="Checked"),
            actor_id=actor,
            trace_id=str(uuid.uuid4()),
        )
    assert [item.concept_id for item in get_approved(db)] == [concept.id]
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.resource_type == kind)
        .order_by(AuditEvent.occurred_at)
    ).all()
    assert [(event.action, event.resource_version) for event in events] == [
        (f"{kind}.create", "1"),
        (f"{kind}.submit", "2"),
        (f"{kind}.approve", "3"),
    ]
    assert all(
        event.actor_id == actor
        and event.resource_id == str(concept.id)
        and event.decision == "allowed"
        for event in events
    )
    concept.status = "draft"
    db.commit()
    assert get_approved(db) == []


def test_failed_audit_rolls_back_creation(catalog_db, monkeypatch):
    db = catalog_db
    actor = uuid.uuid4()
    concept = create_concept(
        db,
        data=ConceptWrite(kind="product", canonical_name="Rollback", status="approved"),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.services.admin.medical_concepts.clinical_entities.common.record_audit_event",
        fail_audit,
    )
    with pytest.raises(RuntimeError):
        create_entity(
            db,
            kind="product",
            data=ProductCreate(concept_id=concept.id),
            actor_id=actor,
            trace_id=str(uuid.uuid4()),
        )
    assert db.scalar(select(Product)) is None


def test_ingredient_amount_requires_source_and_complete_fields():
    values = {
        "concept_id": uuid.uuid4(),
        "reference_amount": Decimal("2.123456"),
        "reference_unit": "mg",
        "reference_basis": "per serving",
    }
    with pytest.raises(ValidationError):
        IngredientCreate(**values)
    assert IngredientCreate(
        **values, source_reference="Source"
    ).reference_amount == Decimal("2.123456")
    with pytest.raises(ValidationError):
        IngredientCreate(
            **{**values, "reference_basis": " ", "source_reference": "Source"}
        )


@pytest.mark.parametrize("operation", ["update", "submit"])
def test_audit_failure_rolls_back_catalog_changes(catalog_db, monkeypatch, operation):
    db = catalog_db
    actor = uuid.uuid4()
    concept = create_concept(
        db,
        data=ConceptWrite(
            kind="product", canonical_name="Audit rollback", status="approved"
        ),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )
    create_entity(
        db,
        kind="product",
        data=ProductCreate(
            concept_id=concept.id, description="Original", source_reference="Source"
        ),
        actor_id=actor,
        trace_id=str(uuid.uuid4()),
    )

    def fail_audit(*args, **kwargs):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(
        "app.services.admin.medical_concepts.clinical_entities.common.record_audit_event",
        fail_audit,
    )
    with pytest.raises(RuntimeError):
        if operation == "update":
            update_entity(
                db,
                kind="product",
                concept_id=concept.id,
                data=ProductUpdate(version=1, description="Changed"),
                actor_id=actor,
                trace_id=str(uuid.uuid4()),
            )
        else:
            transition_entity(
                db,
                kind="product",
                concept_id=concept.id,
                action="submit",
                data=LifecycleRequest(version=1),
                actor_id=actor,
                trace_id=str(uuid.uuid4()),
            )
    product = db.get(Product, concept.id)
    assert product.status == "draft"
    assert product.version == 1
    assert product.description == "Original"
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.resource_type == "product")
    ).all()
    assert [(event.action, event.resource_version) for event in events] == [
        ("product.create", "1")
    ]
