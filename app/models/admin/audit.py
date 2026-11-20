"""Phase 08 - Immutable-style audit event model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class AuditEvent(Base):
    """A historical administrative/security event.

    Audit events have no ORM relationships with cascade
    deletion. Actor IDs remain available even if an
    administrator account is subsequently removed.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_audit_events_occurred_at",
            "occurred_at",
        ),
        Index(
            "ix_audit_events_actor_time",
            "actor_id",
            "occurred_at",
        ),
        Index(
            "ix_audit_events_resource",
            "resource_type",
            "resource_id",
        ),
        Index(
            "ix_audit_events_trace_id",
            "trace_id",
        ),
    )
