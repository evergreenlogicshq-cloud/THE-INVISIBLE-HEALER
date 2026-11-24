"""Phase 09 - Medical concept taxonomy models."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class MedicalConcept(Base):
    """Stable medical terminology identity."""

    __tablename__ = "medical_concepts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    namespace: Mapped[str] = mapped_column(String(60), nullable=False, default="local")
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ontology_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    aliases: Mapped[list["ConceptAlias"]] = relationship(
        back_populates="concept",
        cascade="all, delete-orphan",
        order_by="ConceptAlias.normalized_alias",
    )

    __table_args__ = (
        UniqueConstraint(
            "namespace",
            "normalized_name",
            name="uq_medical_concepts_namespace_name",
        ),
        CheckConstraint(
            "kind IN ("
            "'health_issue', 'symptom', 'medication', "
            "'product', 'remedy', 'ingredient')",
            name="concept_kind",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="concept_status",
        ),
        Index(
            "ix_medical_concepts_kind_status",
            "kind",
            "status",
        ),
    )


class ConceptAlias(Base):
    """A name associated with a medical concept.

    Every concept has exactly one primary alias
    managed by the service layer. The primary
    alias matches its canonical name.
    """

    __tablename__ = "concept_aliases"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "medical_concepts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    namespace: Mapped[str] = mapped_column(String(60), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    concept: Mapped[MedicalConcept] = relationship(back_populates="aliases")

    __table_args__ = (
        UniqueConstraint(
            "namespace",
            "normalized_alias",
            name="uq_concept_aliases_namespace_name",
        ),
        Index(
            "ix_concept_aliases_lookup",
            "normalized_alias",
        ),
    )
