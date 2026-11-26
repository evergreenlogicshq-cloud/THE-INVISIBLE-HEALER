"""Phase 11 - Shared catalog entity ORM fields."""

from sqlalchemy import CheckConstraint, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.admin.medical_concepts.clinical_entities.base import ClinicalEntityMixin


class CatalogEntityMixin(ClinicalEntityMixin):
    """Shared catalog metadata and lifecycle fields."""

    source_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


def catalog_constraints(table_name: str):
    """Return independent constraints for each catalog table."""

    return (
        CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'retired')",
            name="catalog_status",
        ),
        CheckConstraint(
            "version >= 1",
            name="catalog_version",
        ),
        Index(
            f"ix_{table_name}_status",
            "status",
        ),
    )
