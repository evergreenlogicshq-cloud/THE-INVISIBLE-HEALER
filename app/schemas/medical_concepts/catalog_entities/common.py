"""Phase 11 - Catalog entity validation schemas."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.medical_concepts.clinical_entities.common import (
    ClinicalEntityStatus,
    ClinicalEntityWrite,
)

CatalogKind = Literal["product", "remedy", "ingredient"]

ReferenceUnit = Literal["mcg", "mg", "g", "kg", "mL", "L", "IU", "CFU"]


class CatalogWrite(ClinicalEntityWrite):
    """Common editable catalog metadata."""

    source_reference: str | None = Field(default=None, max_length=4000)
    evidence_notes: str | None = Field(default=None, max_length=10000)

    @field_validator("*")
    @classmethod
    def reject_null_characters(cls, value):
        if isinstance(value, str) and "\x00" in value:
            raise ValueError("Text fields cannot contain null characters.")
        return value


class ProductWrite(CatalogWrite):
    """Editable product metadata."""

    manufacturer: str | None = Field(default=None, max_length=200)
    brand: str | None = Field(default=None, max_length=150)
    dosage_form: str | None = Field(default=None, max_length=100)
    product_category: str | None = Field(default=None, max_length=100)
    country_of_origin: str | None = Field(default=None, max_length=100)
    regulatory_number: str | None = Field(default=None, max_length=100)


class RemedyWrite(CatalogWrite):
    """Editable remedy metadata."""

    remedy_type: str | None = Field(default=None, max_length=100)
    preparation: str | None = Field(default=None, max_length=10000)
    administration_route: str | None = Field(default=None, max_length=100)
    limitations: str | None = Field(default=None, max_length=10000)


class IngredientWrite(CatalogWrite):
    """Editable ingredient metadata."""

    scientific_name: str | None = Field(default=None, max_length=250)
    ingredient_type: str | None = Field(default=None, max_length=100)
    source_part: str | None = Field(default=None, max_length=100)
    reference_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
        allow_inf_nan=False,
    )
    reference_unit: ReferenceUnit | None = None
    reference_basis: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_reference_amount(self):
        fields = self.reference_amount, self.reference_unit, self.reference_basis

        if all(value is None for value in fields):
            return self

        if any(value is None for value in fields):
            raise ValueError(
                "Reference amount, unit and basis must be supplied together."
            )

        if not self.reference_basis:
            raise ValueError("Reference basis cannot be empty.")

        if not self.source_reference:
            raise ValueError("A source reference is required for a reference amount.")

        return self


class ProductCreate(ProductWrite):
    concept_id: uuid.UUID


class RemedyCreate(RemedyWrite):
    concept_id: uuid.UUID


class IngredientCreate(IngredientWrite):
    concept_id: uuid.UUID


class ProductUpdate(ProductWrite):
    version: int = Field(ge=1)


class RemedyUpdate(RemedyWrite):
    version: int = Field(ge=1)


class IngredientUpdate(IngredientWrite):
    version: int = Field(ge=1)


class CatalogRead(BaseModel):
    """Common catalog response metadata."""

    model_config = ConfigDict(from_attributes=True)

    concept_id: uuid.UUID
    canonical_name: str
    namespace: str
    kind: CatalogKind
    concept_status: str
    status: ClinicalEntityStatus
    version: int
    created_by: uuid.UUID
    updated_by: uuid.UUID
    reviewed_by: uuid.UUID | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None
    retired_at: datetime | None


class ProductRead(CatalogRead, ProductWrite):
    kind: Literal["product"]


class RemedyRead(CatalogRead, RemedyWrite):
    kind: Literal["remedy"]


class IngredientRead(CatalogRead, IngredientWrite):
    kind: Literal["ingredient"]


CatalogResponse = ProductRead | RemedyRead | IngredientRead


class CatalogList(BaseModel):
    """Paginated catalog response."""

    items: list[CatalogResponse]
    total: int
    page: int
    page_size: int
