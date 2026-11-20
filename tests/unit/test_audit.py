"""Phase 08 - Audit service unit tests."""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.services.admin.audit import (
    list_audit_events,
    record_audit_event,
)


@pytest.fixture
def audit_engine() -> Generator[Engine, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_audit_update_is_blocked(audit_engine):
    with Session(audit_engine) as db:
        created = record_audit_event(
            db,
            actor_type="system",
            action="admin.create",
            resource_type="admin_user",
            decision="allowed",
            trace_id=uuid.uuid4(),
        )
        event_id = created.id
        db.commit()

    with Session(audit_engine) as db:
        event = db.get(AuditEvent, event_id)
        event.action = "admin.delete"

        with pytest.raises(ValueError):
            db.flush()

        db.rollback()


def test_audit_delete_is_blocked(audit_engine):
    with Session(audit_engine) as db:
        created = record_audit_event(
            db,
            actor_type="system",
            action="admin.create",
            resource_type="admin_user",
            decision="allowed",
            trace_id=uuid.uuid4(),
        )
        event_id = created.id
        db.commit()

    with Session(audit_engine) as db:
        event = db.get(AuditEvent, event_id)
        db.delete(event)

        with pytest.raises(ValueError):
            db.flush()

        db.rollback()


def test_list_audit_events_supports_filter(audit_engine):
    with Session(audit_engine) as db:
        for action in ("admin.login", "admin.logout"):
            record_audit_event(
                db,
                actor_type="system",
                action=action,
                resource_type="admin_session",
                decision="allowed",
                trace_id=uuid.uuid4(),
            )
        db.commit()

    with Session(audit_engine) as db:
        events = list_audit_events(
            db,
            action="admin.login",
        )

        assert len(events) == 1
        assert events[0].action == "admin.login"
