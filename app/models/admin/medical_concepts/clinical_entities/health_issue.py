"""Phase 10 - Health issue ORM model."""

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.admin.medical_concepts.clinical_entities.base import ClinicalEntityMixin
from app.models.admin.medical_concepts.concept import MedicalConcept


class HealthIssue(ClinicalEntityMixin, Base):
    """Clinical metadata associated with a health issue concept."""

    __tablename__ = "health_issues"

    body_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinical_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    typical_course: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unknown"
    )
    concept: Mapped[MedicalConcept] = relationship()

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'retired')",
            name="health_issue_status",
        ),
        CheckConstraint(
            "typical_course IN "
            "('acute', 'chronic', 'recurrent', 'variable', 'unknown')",
            name="health_issue_course",
        ),
        CheckConstraint(
            "version >= 1",
            name="health_issue_version",
        ),
        Index(
            "ix_health_issues_status",
            "status",
        ),
    )
