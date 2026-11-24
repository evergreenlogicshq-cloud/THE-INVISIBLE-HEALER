"""Phase 10 - Shared clinical entity ORM fields."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class ClinicalEntityMixin:
    """Shared fields for concept-linked clinical entities."""

    @declared_attr
    def concept_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            Uuid(as_uuid=True),
            ForeignKey(
                "medical_concepts.id",
                ondelete="RESTRICT",
            ),
            primary_key=True,
        )

    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
