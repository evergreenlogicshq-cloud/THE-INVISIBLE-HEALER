"""Phase 09 - Medical taxonomy business operations."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.admin.medical_concepts.clinical_entities import HealthIssue, Symptom
from app.models.admin.medical_concepts.concept import ConceptAlias, MedicalConcept
from app.schemas.medical_concepts.concept import (
    ConceptRead,
    ConceptWrite,
    normalize_label,
)
from app.services.admin.audit import record_audit_event


class ConceptError(Exception):
    pass


class ConceptNotFound(ConceptError):
    pass


class ConceptConflict(ConceptError):
    pass


class ConceptValidationError(ConceptError):
    pass


def get_concept(db: Session, concept_id: uuid.UUID) -> MedicalConcept:
    statement = (
        select(MedicalConcept)
        .options(selectinload(MedicalConcept.aliases))
        .where(MedicalConcept.id == concept_id)
    )

    concept = db.scalar(statement)

    if concept is None:
        raise ConceptNotFound("Medical concept was not found.")

    return concept


def get_concept_for_update(db: Session, concept_id: uuid.UUID) -> MedicalConcept:
    """Lock a medical concept for a terminology write."""

    statement = (
        select(MedicalConcept)
        .options(selectinload(MedicalConcept.aliases))
        .where(MedicalConcept.id == concept_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    concept = db.scalar(statement)

    if concept is None:
        raise ConceptNotFound("Medical concept was not found.")

    return concept


def get_linked_clinical_entity(db: Session, concept_id: uuid.UUID):
    """Find a Phase 10 record associated with the concept."""

    health_issue = db.get(HealthIssue, concept_id)

    if health_issue is not None:
        return health_issue

    return db.get(Symptom, concept_id)


def protect_linked_concept(
    db: Session, concept: MedicalConcept, data: ConceptWrite
) -> None:
    """Prevent terminology changes after subtype linkage."""

    linked = get_linked_clinical_entity(db, concept.id)

    if linked is None:
        return

    current_aliases = {alias.alias for alias in concept.aliases if not alias.is_primary}

    if (
        concept.canonical_name != data.canonical_name
        or concept.ontology_code != data.ontology_code
        or current_aliases != set(data.aliases)
    ):
        raise ConceptValidationError(
            "Terminology is locked because the concept has a linked clinical record."
        )

    if (
        linked.status in {"in_review", "approved"}
        and concept.status == "approved"
        and data.status != "approved"
    ):
        raise ConceptValidationError(
            "Concept approval cannot be withdrawn while its clinical record is active."
        )


def serialize_concept(concept: MedicalConcept) -> ConceptRead:
    return ConceptRead(
        id=concept.id,
        kind=concept.kind,
        namespace=concept.namespace,
        canonical_name=concept.canonical_name,
        normalized_name=concept.normalized_name,
        ontology_code=concept.ontology_code,
        status=concept.status,
        aliases=sorted(
            alias.alias for alias in concept.aliases if not alias.is_primary
        ),
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        retired_at=concept.retired_at,
    )


def list_concepts(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 25,
    kind: str | None = None,
    status: str | None = None,
    query: str | None = None,
) -> tuple[list[MedicalConcept], int]:

    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("Invalid pagination parameters.")

    statement = select(MedicalConcept)
    count_statement = select(func.count(MedicalConcept.id))

    conditions = []

    if kind:
        conditions.append(MedicalConcept.kind == kind)

    if status:
        conditions.append(MedicalConcept.status == status)

    if query and query.strip():
        normalized = normalize_label(query)

        matching_ids = select(ConceptAlias.concept_id).where(
            ConceptAlias.normalized_alias.contains(normalized, autoescape=True)
        )

        conditions.append(MedicalConcept.id.in_(matching_ids))

    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = db.scalar(count_statement) or 0

    statement = (
        statement.options(selectinload(MedicalConcept.aliases))
        .order_by(
            MedicalConcept.canonical_name,
            MedicalConcept.id,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return list(db.scalars(statement).all()), total


def replace_aliases(db: Session, concept: MedicalConcept, data: ConceptWrite) -> None:
    """Keep one primary alias and replace synonyms.

    A savepoint allows a failed update to be rolled
    back without leaving partial alias mutations.
    """

    old_aliases = list(concept.aliases)

    for alias in old_aliases:
        db.delete(alias)

    db.flush()

    names = [
        (data.canonical_name, True),
        *((name, False) for name in data.aliases),
    ]

    for name, primary in names:
        db.add(
            ConceptAlias(
                concept_id=concept.id,
                namespace=data.namespace,
                alias=name,
                normalized_alias=normalize_label(name),
                language="en",
                is_primary=primary,
            )
        )

    db.flush()

    # Rebuild the loaded relationship after replacing
    # rows, so the response includes the new aliases.
    db.expire(concept, ["aliases"])


def create_concept(
    db: Session,
    *,
    data: ConceptWrite,
    actor_id: uuid.UUID,
    trace_id: str,
) -> MedicalConcept:
    """Create the concept, aliases and audit atomically."""

    try:
        with db.begin_nested():
            concept = MedicalConcept(
                kind=data.kind,
                namespace=data.namespace,
                canonical_name=data.canonical_name,
                normalized_name=normalize_label(data.canonical_name),
                ontology_code=data.ontology_code,
                status=data.status,
                created_by=actor_id,
                updated_by=actor_id,
            )

            db.add(concept)
            db.flush()

            replace_aliases(db, concept, data)

            record_audit_event(
                db,
                action="medical_concept.create",
                resource_type="medical_concept",
                resource_id=concept.id,
                actor_id=actor_id,
                trace_id=trace_id,
                decision="allowed",
            )

        db.commit()
        return get_concept(db, concept.id)

    except IntegrityError as exc:
        db.rollback()
        raise ConceptConflict(
            "A canonical name or alias already exists in this terminology namespace."
        ) from exc

    except Exception:
        db.rollback()
        raise


def update_concept(
    db: Session,
    *,
    concept_id: uuid.UUID,
    data: ConceptWrite,
    actor_id: uuid.UUID,
    trace_id: str,
) -> MedicalConcept:

    try:
        with db.begin_nested():
            concept = get_concept_for_update(db, concept_id)

            if concept.status == "retired":
                raise ConceptValidationError("Retired concepts cannot be edited.")

            if concept.kind != data.kind:
                raise ConceptValidationError("Concept kind cannot be changed.")

            if concept.namespace != data.namespace:
                raise ConceptValidationError("Concept namespace cannot be changed.")

            protect_linked_concept(db, concept, data)

            current_aliases = {
                alias.alias for alias in concept.aliases if not alias.is_primary
            }

            terminology_changed = (
                concept.canonical_name != data.canonical_name
                or current_aliases != set(data.aliases)
            )
            concept.canonical_name = data.canonical_name
            concept.normalized_name = normalize_label(data.canonical_name)
            concept.ontology_code = data.ontology_code
            concept.status = data.status
            concept.updated_by = actor_id
            concept.updated_at = datetime.now(UTC)

            # Preserve existing alias IDs if terminology
            # has not changed.
            if terminology_changed:
                replace_aliases(db, concept, data)

            record_audit_event(
                db,
                action="medical_concept.update",
                resource_type="medical_concept",
                resource_id=concept.id,
                actor_id=actor_id,
                trace_id=trace_id,
                decision="allowed",
            )

        db.commit()

        return get_concept(
            db,
            concept_id,
        )

    except IntegrityError as exc:
        db.rollback()

        raise ConceptConflict(
            "A canonical name or alias conflicts with an existing medical concept."
        ) from exc

    except Exception:
        db.rollback()
        raise


def retire_concept(
    db: Session,
    *,
    concept_id: uuid.UUID,
    actor_id: uuid.UUID,
    trace_id: str,
) -> MedicalConcept:
    """Soft-retire a concept without invalidating active subtypes."""

    try:
        with db.begin_nested():
            concept = get_concept_for_update(
                db,
                concept_id,
            )

            linked = get_linked_clinical_entity(
                db,
                concept_id,
            )

            if linked is not None and linked.status != "retired":
                raise ConceptConflict(
                    "Retire the linked clinical record "
                    "before retiring this medical concept."
                )

            if concept.status != "retired":
                now = datetime.now(UTC)

                concept.status = "retired"
                concept.retired_at = now
                concept.updated_at = now
                concept.updated_by = actor_id

                record_audit_event(
                    db,
                    action="medical_concept.retire",
                    resource_type="medical_concept",
                    resource_id=concept.id,
                    actor_id=actor_id,
                    trace_id=trace_id,
                    decision="allowed",
                )

        db.commit()

        return get_concept(db, concept_id)

    except Exception:
        db.rollback()
        raise


def resolve_concept(
    db: Session,
    *,
    term: str,
    namespace: str = "local",
    include_retired: bool = False,
) -> MedicalConcept | None:
    """Exact normalized terminology lookup.

    This does not perform clinical interpretation.
    """

    statement = (
        select(MedicalConcept)
        .join(
            ConceptAlias,
            ConceptAlias.concept_id == MedicalConcept.id,
        )
        .where(
            ConceptAlias.namespace == namespace,
            ConceptAlias.normalized_alias == normalize_label(term),
        )
    )

    if not include_retired:
        statement = statement.where(MedicalConcept.status != "retired")

    return db.scalar(statement)
