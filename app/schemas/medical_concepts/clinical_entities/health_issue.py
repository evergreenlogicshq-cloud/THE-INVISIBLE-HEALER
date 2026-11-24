"""Phase 10 - Health issue validation schemas."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.medical_concepts.clinical_entities.common import (
    ClinicalEntityRead,
    ClinicalEntityWrite,
)

TypicalCourse = Literal["acute", "chronic", "recurrent", "variable", "unknown"]


class HealthIssueWrite(ClinicalEntityWrite):
    """Editable health issue fields."""

    body_system: str | None = Field(default=None, max_length=100)
    clinical_category: str | None = Field(default=None, max_length=100)
    typical_course: TypicalCourse = "unknown"


class HealthIssueCreate(HealthIssueWrite):
    """Create a concept-linked health issue."""

    concept_id: uuid.UUID


class HealthIssueUpdate(HealthIssueWrite):
    """Update an existing draft health issue."""

    version: int = Field(ge=1)


class HealthIssueRead(ClinicalEntityRead):
    """Complete health issue response."""

    body_system: str | None
    clinical_category: str | None
    typical_course: TypicalCourse


class HealthIssueList(BaseModel):
    items: list[HealthIssueRead]
    total: int
    page: int
    page_size: int
