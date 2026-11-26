"""Phase 11 - Remedy ORM model."""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.admin.medical_concepts.catalog_entities.base import (
    CatalogEntityMixin,
    catalog_constraints,
)
from app.models.admin.medical_concepts.concept import MedicalConcept


class Remedy(CatalogEntityMixin, Base):
    """Non-product remedy catalog metadata."""

    __tablename__ = "remedies"

    remedy_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preparation: Mapped[str | None] = mapped_column(Text, nullable=True)
    administration_route: Mapped[str | None] = mapped_column(String(100), nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    concept: Mapped[MedicalConcept] = relationship()

    __table_args__ = catalog_constraints("remedies")
