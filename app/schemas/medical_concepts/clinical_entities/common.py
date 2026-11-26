"""Phase 10 - Shared clinical entity schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ClinicalEntityKind = Literal[
    "health_issue",
    "symptom",
    "product",
    "remedy",
    "ingredient",
]


ClinicalEntityStatus = Literal["draft", "in_review", "approved", "retired"]
LifecycleAction = Literal["submit", "approve", "reject", "retire"]


class ClinicalEntityWrite(BaseModel):
    """Common writable clinical metadata."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    description: str = Field(default="", max_length=10000)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Invalid description.")

        return value


class LifecycleRequest(BaseModel):
    """Version-controlled lifecycle operation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    version: int = Field(ge=1)
    notes: str | None = Field(default=None, max_length=2000)


class ConceptOption(BaseModel):
    """Autocomplete response."""

    id: uuid.UUID
    canonical_name: str
    namespace: str
    status: str


class ClinicalEntityRead(BaseModel):
    """Common clinical entity response."""

    model_config = ConfigDict(from_attributes=True)

    concept_id: uuid.UUID
    canonical_name: str
    namespace: str
    kind: ClinicalEntityKind
    concept_status: str
    description: str
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
