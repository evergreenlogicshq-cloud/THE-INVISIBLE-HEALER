"""Phase 08 - Audit recording service.

All audit writes use the caller's SQLAlchemy Session.

The caller owns the transaction:
    business write + audit write -> one commit

Do not commit independently in this service.
"""

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.admin.audit import AuditEvent

logger = logging.getLogger(__name__)


VALID_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]*$")
VALID_DECISIONS = frozenset({"allowed", "denied", "failed"})
VALID_ACTORS = frozenset({"doctor_admin", "system"})

# These fields must never be accepted as
# audit resource identifiers or resource versions.
SENSITIVE_NAMES = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "csrf_secret",
        "session_secret",
        "api_key",
        "authorization",
        "cookie",
        "patient_message",
        "message_content",
    }
)


def _validate_name(value: str, field: str) -> str:
    if (
        not isinstance(value, str)
        or not VALID_IDENTIFIER.fullmatch(value)
        or len(value) > 80
    ):
        raise ValueError(f"Invalid {field}")

    if any(item in value.split(".") for item in SENSITIVE_NAMES):
        raise ValueError(f"Sensitive {field} is forbidden")

    return value


def _safe_reference(
    value: str | uuid.UUID | int | None,
    maximum: int,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, (str, uuid.UUID, int)):
        raise ValueError("Reference must be a scalar identifier")  # noqa: TRY004

    result = str(value)

    if (
        not result
        or len(result) > maximum
        or not re.fullmatch(r"[A-Za-z0-9_.:-]+", result)
    ):
        raise ValueError("Invalid audit reference")

    return result


def record_audit_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    decision: str,
    trace_id: str | uuid.UUID,
    actor_id: uuid.UUID | None = None,
    actor_type: str = "doctor_admin",
    resource_id: str | uuid.UUID | int | None = None,
    resource_version: str | int | None = None,
) -> AuditEvent:
    """Add one audit event to the current transaction.

    No secrets, request bodies, patient messages,
    or arbitrary metadata are accepted.
    """

    action = _validate_name(action, "action")
    resource_type = _validate_name(resource_type, "resource_type")

    if len(action) > 100:
        raise ValueError("Action is too long")

    if decision not in VALID_DECISIONS:
        raise ValueError("Invalid audit decision")

    if actor_type not in VALID_ACTORS:
        raise ValueError("Invalid actor type")

    if actor_type == "doctor_admin" and actor_id is None:
        raise ValueError("Doctor audit events require actor_id")

    if actor_id is not None and not isinstance(actor_id, uuid.UUID):
        raise ValueError("Actor ID must be a UUID")

    trace = str(uuid.UUID(str(trace_id)))

    event = AuditEvent(
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=_safe_reference(resource_id, 100),
        resource_version=_safe_reference(resource_version, 80),
        decision=decision,
        trace_id=trace,
        occurred_at=datetime.now(UTC),
    )

    db.add(event)

    # Flush within the same transaction.
    # SQL errors propagate so the business
    # transaction cannot silently succeed.
    db.flush()

    logger.info(
        "Audit event recorded: id=%s action=%s trace=%s",
        event.id,
        action,
        trace,
    )

    return event


def list_audit_events(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
) -> list[AuditEvent]:
    """Read audit events newest first."""

    if not 1 <= limit <= 101:
        raise ValueError("Limit must be between 1 and 101")

    if offset < 0 or offset > 10000:
        raise ValueError("Invalid offset")

    statement = select(AuditEvent)

    if action:
        statement = statement.where(
            AuditEvent.action == _validate_name(action, "action")
        )

    statement = (
        statement.order_by(
            AuditEvent.occurred_at.desc(),
            AuditEvent.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


def prevent_audit_modification(db: Session) -> None:
    """Reject ORM modifications to existing audit events.

    PostgreSQL database triggers provide the stronger
    persistence-layer enforcement in production.
    """
    for item in db.dirty:
        if isinstance(item, AuditEvent) and inspect(item).modified:
            raise ValueError("Audit events cannot be updated")

    for item in db.deleted:
        if isinstance(item, AuditEvent):
            raise ValueError("Audit events cannot be deleted")  # noqa: TRY004


from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.orm import Session as SQLAlchemySession


@sqlalchemy_event.listens_for(
    SQLAlchemySession,
    "before_flush",
)
def reject_existing_audit_changes(
    session,
    flush_context,
    instances,
):
    """Reject audit updates/deletes before flushing."""
    prevent_audit_modification(session)
