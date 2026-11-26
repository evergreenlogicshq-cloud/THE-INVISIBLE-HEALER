"""Phase 11 - Product ORM model."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.admin.medical_concepts.catalog_entities.base import (
    CatalogEntityMixin,
    catalog_constraints,
)
from app.models.admin.medical_concepts.concept import MedicalConcept


class Product(CatalogEntityMixin, Base):
    """Product catalog metadata linked to a medical concept."""

    __tablename__ = "products"

    manufacturer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(150), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    regulatory_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    concept: Mapped[MedicalConcept] = relationship()

    __table_args__ = catalog_constraints("products")
