"""Phase 10 - Seed synthetic clinical catalog examples."""

import argparse
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import create_database_engine, create_session_factory
from app.models.admin.admin_user import AdminUser
from app.models.admin.clinical_entities import HealthIssue, Symptom
from app.models.admin.concept import MedicalConcept
from app.schemas.clinical_entities import HealthIssueCreate, SymptomCreate
from app.schemas.concept import ConceptWrite, normalize_label
from app.services.admin.clinical_entities.health_issue import create_health_issue
from app.services.admin.clinical_entities.symptom import create_symptom
from app.services.admin.concepts import create_concept

NAMESPACE = "phase10_demo"

HEALTH_ISSUES = ["Migraine", "Gastroesophageal Reflux Disease", "Osteoarthritis"]
SYMPTOMS = ["Headache", "Nausea", "Joint Pain", "Heartburn", "Fatigue"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Phase 10 draft catalog examples."
    )
    parser.add_argument("--admin-email", required=True)
    args = parser.parse_args()
    settings = get_settings()

    if settings.APP_ENV not in {"development", "testing"}:
        raise SystemExit(
            "Seed script is restricted to development and testing environments."
        )

    engine = create_database_engine(settings)
    factory = create_session_factory(engine)

    created = 0
    skipped = 0

    try:
        with factory() as db:
            actor = db.scalar(
                select(AdminUser).where(
                    AdminUser.email == args.admin_email.strip().casefold(),
                    AdminUser.is_active.is_(True),
                )
            )

            if actor is None:
                raise SystemExit("Active doctor administrator not found.")

            actor_id = actor.id

            groups = (
                (
                    "health_issue",
                    HEALTH_ISSUES,
                    HealthIssue,
                ),
                (
                    "symptom",
                    SYMPTOMS,
                    Symptom,
                ),
            )

            for kind, names, model in groups:
                for name in names:
                    concept = db.scalar(
                        select(MedicalConcept).where(
                            MedicalConcept.namespace == NAMESPACE,
                            MedicalConcept.normalized_name == normalize_label(name),
                        )
                    )

                    if concept is None:
                        concept = create_concept(
                            db,
                            data=ConceptWrite(
                                kind=kind,
                                namespace=NAMESPACE,
                                canonical_name=name,
                                status="draft",
                            ),
                            actor_id=actor_id,
                            trace_id=str(uuid.uuid4()),
                        )

                    if concept.kind != kind or concept.status == "retired":
                        skipped += 1
                        continue

                    existing = db.get(model, concept.id)

                    if existing is not None:
                        skipped += 1
                        continue

                    description = (
                        "Synthetic demonstration record. Not clinically validated."
                    )

                    if kind == "health_issue":
                        create_health_issue(
                            db,
                            data=HealthIssueCreate(
                                concept_id=concept.id,
                                description=description,
                            ),
                            actor_id=actor_id,
                            trace_id=str(uuid.uuid4()),
                        )

                    else:
                        create_symptom(
                            db,
                            data=SymptomCreate(
                                concept_id=concept.id,
                                description=description,
                            ),
                            actor_id=actor_id,
                            trace_id=str(uuid.uuid4()),
                        )

                    created += 1

        print(f"Created: {created}; Skipped: {skipped}")

        print("All seeded records are drafts and require clinical review.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
