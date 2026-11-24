"""Phase 10 - Shared clinical entity business operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.admin.clinical_entities import HealthIssue, Symptom
from app.models.admin.concept import ConceptAlias, MedicalConcept
from app.schemas.clinical_entities import (
    ClinicalEntityKind,
    ConceptOption,
    HealthIssueCreate,
    HealthIssueRead,
    HealthIssueUpdate,
    LifecycleAction,
    LifecycleRequest,
    SymptomCreate,
    SymptomRead,
    SymptomUpdate,
)
from app.schemas.concept import normalize_label
from app.services.admin.audit import record_audit_event

ClinicalEntity = HealthIssue | Symptom
CreateData = HealthIssueCreate | SymptomCreate
UpdateData = HealthIssueUpdate | SymptomUpdate


class ClinicalEntityError(Exception):
    pass


class ClinicalEntityNotFound(ClinicalEntityError):
    pass


class ClinicalEntityConflict(ClinicalEntityError):
    pass


class ClinicalEntityValidationError(ClinicalEntityError):
    pass


def model_for_kind(kind: ClinicalEntityKind):
    if kind == "health_issue":
        return HealthIssue

    if kind == "symptom":
        return Symptom

    raise ClinicalEntityValidationError("Unsupported clinical entity kind.")


def get_locked_concept(db: Session, concept_id: uuid.UUID) -> MedicalConcept:
    """Lock the parent concept before subtype modifications."""

    statement = (
        select(MedicalConcept)
        .where(MedicalConcept.id == concept_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    concept = db.scalar(statement)

    if concept is None:
        raise ClinicalEntityNotFound("Medical concept was not found.")

    return concept


def validate_concept(
    concept: MedicalConcept,
    kind: ClinicalEntityKind,
    *,
    require_approved: bool = False,
) -> None:
    if concept.kind != kind:
        raise ClinicalEntityValidationError(
            "Medical concept kind does not match the requested entity."
        )

    if concept.status == "retired":
        raise ClinicalEntityConflict("Retired concepts cannot be used.")

    if require_approved and concept.status != "approved":
        raise ClinicalEntityConflict("The medical concept must be approved first.")


def get_entity(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    concept_id: uuid.UUID,
    lock: bool = False,
) -> ClinicalEntity:
    model = model_for_kind(kind)

    statement = (
        select(model)
        .where(model.concept_id == concept_id)
        .options(selectinload(model.concept))
    )

    if lock:
        statement = statement.with_for_update().execution_options(
            populate_existing=True
        )

    entity = db.scalar(statement)

    if entity is None:
        raise ClinicalEntityNotFound("Clinical entity was not found.")

    return entity


def check_version(entity: ClinicalEntity, expected_version: int) -> None:
    if entity.version != expected_version:
        raise ClinicalEntityConflict("The record has changed. Refresh and try again.")


def serialize_entity(entity: ClinicalEntity) -> HealthIssueRead | SymptomRead:
    data = {
        "concept_id": entity.concept_id,
        "canonical_name": entity.concept.canonical_name,
        "namespace": entity.concept.namespace,
        "kind": entity.concept.kind,
        "concept_status": entity.concept.status,
        "description": entity.description,
        "status": entity.status,
        "version": entity.version,
        "created_by": entity.created_by,
        "updated_by": entity.updated_by,
        "reviewed_by": entity.reviewed_by,
        "review_notes": entity.review_notes,
        "created_at": entity.created_at,
        "updated_at": entity.updated_at,
        "reviewed_at": entity.reviewed_at,
        "retired_at": entity.retired_at,
    }

    if isinstance(entity, HealthIssue):
        return HealthIssueRead(
            **data,
            body_system=entity.body_system,
            clinical_category=entity.clinical_category,
            typical_course=entity.typical_course,
        )

    return SymptomRead(
        **data,
        body_location=entity.body_location,
        symptom_category=entity.symptom_category,
        observation_type=entity.observation_type,
    )


def list_entities(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    page: int = 1,
    page_size: int = 20,
    query: str | None = None,
    entity_status: str | None = None,
) -> tuple[list[ClinicalEntity], int]:
    """Search and paginate clinical records."""

    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination parameters.")

    model = model_for_kind(kind)

    statement = (
        select(model)
        .join(
            MedicalConcept,
            MedicalConcept.id == model.concept_id,
        )
        .options(selectinload(model.concept))
    )

    count_statement = (
        select(func.count(model.concept_id))
        .select_from(model)
        .join(
            MedicalConcept,
            MedicalConcept.id == model.concept_id,
        )
    )

    conditions = []

    if entity_status:
        conditions.append(model.status == entity_status)

    if query and query.strip():
        normalized = normalize_label(query)

        matching_ids = select(ConceptAlias.concept_id).where(
            ConceptAlias.normalized_alias.contains(
                normalized,
                autoescape=True,
            )
        )

        conditions.append(model.concept_id.in_(matching_ids))

    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = db.scalar(count_statement) or 0

    statement = (
        statement.order_by(
            MedicalConcept.normalized_name,
            MedicalConcept.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return list(db.scalars(statement).all()), total


def search_available_concepts(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    query: str,
    limit: int = 20,
) -> list[ConceptOption]:
    """Search concepts not already linked to a subtype."""

    normalized = normalize_label(query)

    if not normalized:
        return []

    model = model_for_kind(kind)
    matching_ids = select(ConceptAlias.concept_id).where(
        ConceptAlias.normalized_alias.contains(
            normalized,
            autoescape=True,
        )
    )

    used_ids = select(model.concept_id)
    statement = (
        select(MedicalConcept)
        .where(
            MedicalConcept.kind == kind,
            MedicalConcept.status.in_(["draft", "approved"]),
            MedicalConcept.id.in_(matching_ids),
            MedicalConcept.id.not_in(used_ids),
        )
        .order_by(
            MedicalConcept.normalized_name,
            MedicalConcept.id,
        )
        .limit(min(max(limit, 1), 50))
    )

    return [
        ConceptOption(
            id=concept.id,
            canonical_name=concept.canonical_name,
            namespace=concept.namespace,
            status=concept.status,
        )
        for concept in db.scalars(statement).all()
    ]


def audit_entity(
    db: Session,
    *,
    entity: ClinicalEntity,
    kind: ClinicalEntityKind,
    action: str,
    actor_id: uuid.UUID,
    trace_id: str,
) -> None:
    """Reuse the Phase 8 transactional audit service."""

    record_audit_event(
        db,
        action=f"{kind}.{action}",
        resource_type=kind,
        resource_id=entity.concept_id,
        resource_version=entity.version,
        actor_id=actor_id,
        trace_id=trace_id,
        decision="allowed",
    )


def create_entity(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    data: CreateData,
    actor_id: uuid.UUID,
    trace_id: str,
) -> ClinicalEntity:
    """Create a new draft clinical entity."""

    if kind == "health_issue":
        expected_schema = HealthIssueCreate
    else:
        expected_schema = SymptomCreate

    if not isinstance(data, expected_schema):
        raise ClinicalEntityValidationError("Invalid clinical entity payload.")

    model = model_for_kind(kind)

    try:
        concept = get_locked_concept(db, data.concept_id)
        validate_concept(concept, kind)
        existing = db.get(model, data.concept_id)

        if existing is not None:
            raise ClinicalEntityConflict("This concept already has a clinical record.")

        entity = model(
            **data.model_dump(),
            status="draft",
            version=1,
            created_by=actor_id,
            updated_by=actor_id,
        )

        db.add(entity)
        db.flush()

        audit_entity(
            db,
            entity=entity,
            kind=kind,
            action="create",
            actor_id=actor_id,
            trace_id=trace_id,
        )

        db.commit()
        db.refresh(entity)

        return entity

    except IntegrityError as exc:
        db.rollback()

        raise ClinicalEntityConflict(
            "Clinical record conflicts with existing data."
        ) from exc

    except Exception:
        db.rollback()
        raise


def update_entity(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    concept_id: uuid.UUID,
    data: UpdateData,
    actor_id: uuid.UUID,
    trace_id: str,
) -> ClinicalEntity:
    """Update draft metadata with stale-write protection."""

    if kind == "health_issue":
        expected_schema = HealthIssueUpdate
    else:
        expected_schema = SymptomUpdate

    if not isinstance(data, expected_schema):
        raise ClinicalEntityValidationError("Invalid clinical entity payload.")

    try:
        concept = get_locked_concept(db, concept_id)
        validate_concept(concept, kind)
        entity = get_entity(
            db,
            kind=kind,
            concept_id=concept_id,
            lock=True,
        )
        check_version(entity, data.version)

        if entity.status != "draft":
            raise ClinicalEntityConflict("Only draft clinical records can be edited.")

        fields = data.model_dump(exclude={"version"})

        for key, value in fields.items():
            setattr(entity, key, value)

        entity.version += 1
        entity.updated_by = actor_id
        entity.updated_at = datetime.now(UTC)

        entity.reviewed_by = None
        entity.reviewed_at = None
        entity.review_notes = None

        db.flush()

        audit_entity(
            db,
            entity=entity,
            kind=kind,
            action="update",
            actor_id=actor_id,
            trace_id=trace_id,
        )

        db.commit()
        db.refresh(entity)

        return entity

    except Exception:
        db.rollback()
        raise


def transition_entity(
    db: Session,
    *,
    kind: ClinicalEntityKind,
    concept_id: uuid.UUID,
    action: LifecycleAction,
    data: LifecycleRequest,
    actor_id: uuid.UUID,
    trace_id: str,
) -> ClinicalEntity:
    """Apply a controlled clinical review transition."""

    try:
        concept = get_locked_concept(db, concept_id)
        entity = get_entity(
            db,
            kind=kind,
            concept_id=concept_id,
            lock=True,
        )
        check_version(entity, data.version)

        if entity.status == "retired":
            raise ClinicalEntityConflict("Retired records cannot be modified.")

        if action != "retire":
            validate_concept(concept, kind)

        now = datetime.now(UTC)

        if action == "submit":
            if entity.status != "draft":
                raise ClinicalEntityConflict("Only drafts can be submitted.")

            if not entity.description.strip():
                raise ClinicalEntityValidationError(
                    "A description is required before review."
                )

            entity.status = "in_review"

        elif action == "approve":
            if entity.status != "in_review":
                raise ClinicalEntityConflict("Only records in review can be approved.")

            validate_concept(
                concept,
                kind,
                require_approved=True,
            )

            if not data.notes:
                raise ClinicalEntityValidationError("Approval requires review notes.")

            entity.status = "approved"
            entity.reviewed_by = actor_id
            entity.reviewed_at = now
            entity.review_notes = data.notes

        elif action == "reject":
            if entity.status != "in_review":
                raise ClinicalEntityConflict("Only records in review can be rejected.")

            if not data.notes:
                raise ClinicalEntityValidationError("A rejection reason is required.")

            entity.status = "draft"
            entity.reviewed_by = actor_id
            entity.reviewed_at = now
            entity.review_notes = data.notes

        elif action == "retire":
            entity.status = "retired"
            entity.retired_at = now

        else:
            raise ClinicalEntityValidationError("Unsupported lifecycle action.")

        entity.version += 1
        entity.updated_by = actor_id
        entity.updated_at = now

        db.flush()

        audit_entity(
            db,
            entity=entity,
            kind=kind,
            action=action,
            actor_id=actor_id,
            trace_id=trace_id,
        )

        db.commit()
        db.refresh(entity)

        return entity

    except Exception:
        db.rollback()
        raise


def list_approved_entities(
    db: Session,
    *,
    kind: ClinicalEntityKind,
) -> list[ClinicalEntity]:
    """Return approved terminology and subtype records.

    This does not authorize clinical recommendations.
    """

    model = model_for_kind(kind)

    statement = (
        select(model)
        .join(
            MedicalConcept,
            MedicalConcept.id == model.concept_id,
        )
        .where(
            model.status == "approved",
            MedicalConcept.status == "approved",
            MedicalConcept.kind == kind,
        )
        .options(selectinload(model.concept))
        .order_by(MedicalConcept.normalized_name)
    )

    return list(db.scalars(statement).all())
