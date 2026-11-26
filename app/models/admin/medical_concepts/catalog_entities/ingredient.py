"""Phase 11 - Ingredient ORM model."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.admin.medical_concepts.catalog_entities.base import (
    CatalogEntityMixin,
    catalog_constraints,
)
from app.models.admin.medical_concepts.concept import MedicalConcept


class Ingredient(CatalogEntityMixin, Base):
    """Canonical ingredient catalog metadata."""

    __tablename__ = "ingredients"

    scientific_name: Mapped[str | None] = mapped_column(String(250), nullable=True)
    ingredient_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_part: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reference_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    reference_unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_basis: Mapped[str | None] = mapped_column(String(200), nullable=True)
    concept: Mapped[MedicalConcept] = relationship()

    __table_args__ = (
        *catalog_constraints("ingredients"),
        CheckConstraint(
            "reference_amount IS NULL OR reference_amount > 0",
            name="reference_amount_positive",
        ),
        CheckConstraint(
            "("
            "reference_amount IS NULL AND "
            "reference_unit IS NULL AND "
            "reference_basis IS NULL"
            ") OR ("
            "reference_amount IS NOT NULL AND "
            "reference_unit IS NOT NULL AND "
            "reference_basis IS NOT NULL"
            ")",
            name="reference_amount_complete",
        ),
    )
