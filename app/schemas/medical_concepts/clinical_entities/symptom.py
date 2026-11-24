"""Phase 10 - Symptom validation schemas."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.medical_concepts.clinical_entities.common import (
    ClinicalEntityRead,
    ClinicalEntityWrite,
)

ObservationType = Literal["subjective", "objective", "both", "unknown"]


class SymptomWrite(ClinicalEntityWrite):
    """Editable symptom fields."""

    body_location: str | None = Field(default=None, max_length=100)
    symptom_category: str | None = Field(default=None, max_length=100)
    observation_type: ObservationType = "unknown"


class SymptomCreate(SymptomWrite):
    """Create a concept-linked symptom."""

    concept_id: uuid.UUID


class SymptomUpdate(SymptomWrite):
    """Update an existing draft symptom."""

    version: int = Field(ge=1)


class SymptomRead(ClinicalEntityRead):
    """Complete symptom response."""

    body_location: str | None
    symptom_category: str | None
    observation_type: ObservationType


class SymptomList(BaseModel):
    items: list[SymptomRead]
    total: int
    page: int
    page_size: int
