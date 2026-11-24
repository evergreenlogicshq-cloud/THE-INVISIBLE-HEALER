"""Phase 10 - Symptom ORM model."""

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.admin.clinical_entities.base import ClinicalEntityMixin
from app.models.admin.concept import MedicalConcept


class Symptom(ClinicalEntityMixin, Base):
    """Clinical metadata associated with a symptom concept."""

    __tablename__ = "symptoms"

    body_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symptom_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    concept: Mapped[MedicalConcept] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'retired')",
            name="symptom_status",
        ),
        CheckConstraint(
            "observation_type IN ('subjective', 'objective', 'both', 'unknown')",
            name="symptom_observation_type",
        ),
        CheckConstraint(
            "version >= 1",
            name="symptom_version",
        ),
        Index(
            "ix_symptoms_status",
            "status",
        ),
    )
