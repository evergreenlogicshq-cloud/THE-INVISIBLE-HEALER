"""Phase 09 - Medical concept API contracts."""

import re
import unicodedata
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ConceptKind = Literal[
    "health_issue",
    "symptom",
    "medication",
    "product",
    "remedy",
    "ingredient",
]

ConceptStatus = Literal["draft", "approved", "retired"]


def normalize_label(value: str) -> str:
    """Normalize terminology without stripping accents.

    NFKC handles Unicode compatibility characters.
    casefold supports Unicode case-insensitive lookup.
    Whitespace is collapsed deterministically.
    """

    text = unicodedata.normalize("NFKC", value)
    text = " ".join(text.split())
    return text.casefold()


def clean_label(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = " ".join(value.split())

    if not value:
        raise ValueError("A Medical lable cannot be empty")

    if len(value) > 200:
        raise ValueError("A Medical lable is too long")

    if any(unicodedata.category(ch).startswith("C") for ch in value):
        raise ValueError("Control characters are not permitted")

    return value


class ConceptWrite(BaseModel):
    """Fields accepted when creating or editing."""

    kind: ConceptKind
    namespace: str = Field(default="local", min_length=1, max_length=60)
    canonical_name: str = Field(min_length=1, max_length=200)
    ontology_code: str | None = Field(default=None, max_length=100)
    status: Literal["draft", "approved"] = "draft"
    aliases: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("canonical_name")
    @classmethod
    def validate_canonical(cls, value: str) -> str:
        return clean_label(value)

    @field_validator("aliases")
    @classmethod
    def validate_aliases(cls, values: list[str]) -> list[str]:
        return [clean_label(value) for value in values]

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, value: str) -> str:
        value = value.strip().casefold()

        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,59}", value):
            raise ValueError("Invalid terminology namespace.")

        return value

    @field_validator("ontology_code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_name_uniqueness(self):
        names = [self.canonical_name, *self.aliases]
        normalized = [normalize_label(name) for name in names]

        if len(normalized) != len(set(normalized)):
            raise ValueError("Canonical name and aliases must be distinct.")

        return self


class ConceptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: ConceptKind
    namespace: str
    canonical_name: str
    normalized_name: str
    ontology_code: str | None
    status: ConceptStatus
    aliases: list[str]
    created_at: datetime
    updated_at: datetime
    retired_at: datetime | None


class ConceptList(BaseModel):
    items: list[ConceptRead]
    total: int
    page: int
    page_size: int
