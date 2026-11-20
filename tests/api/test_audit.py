"""Phase 08 - Audit endpoint integration tests."""

import re
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.models.admin.audit import AuditEvent
from app.services.admin.auth import create_admin_user

EMAIL = "audit-doctor@example.com"
PASSWORD = "Audit-Doctor-Password-2026!"


@pytest.fixture
def audit_client(
    app: FastAPI,
    test_engine: Engine,
    test_settings: Settings,
) -> Generator[TestClient, None, None]:
    test_settings.ADMIN_SESSIONS_ENABLED = True
    test_settings.SESSION_SECRET = SecretStr(
        "audit-test-session-secret-at-least-32-chars"
    )
    test_settings.SESSION_COOKIE_SECURE = False
    test_settings.SESSION_MAX_AGE_SECONDS = 3600
    test_settings.SESSION_IDLE_TIMEOUT_SECONDS = 900

    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as db:
            create_admin_user(
                db,
                email=EMAIL,
                full_name="Audit Test Doctor",
                password=PASSWORD,
            )
            db.commit()

        with TestClient(app) as client:
            login_page = client.get("/admin/login")
            assert login_page.status_code == 200
            match = re.search(
                r'name="csrf_token"\s+value="([^"]+)"',
                login_page.text,
            )
            assert match is not None
            response = client.post(
                "/admin/login",
                data={
                    "email": EMAIL,
                    "password": PASSWORD,
                    "csrf_token": match.group(1),
                },
                follow_redirects=False,
            )

            assert response.status_code == 303
            yield client

    finally:
        Base.metadata.drop_all(test_engine)


def test_audit_requires_authentication(client):
    response = client.get("/admin/audit")

    # Authentication disabled by default
    # in the shared test configuration.
    assert response.status_code == 503


def test_logged_in_doctor_can_view_audit(audit_client):
    response = audit_client.get("/admin/audit")
    assert response.status_code == 200
    assert "Audit Trail" in response.text
    assert "admin.login" in response.text


def test_audit_page_is_not_cached(audit_client):
    response = audit_client.get("/admin/audit")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]


def test_audit_does_not_expose_secrets(audit_client):
    response = audit_client.get("/admin/audit")
    assert PASSWORD not in response.text
    assert "password_hash" not in response.text
    assert "csrf_secret" not in response.text
    assert "token_hash" not in response.text


def test_login_creates_attributable_event(audit_client, test_engine):
    with Session(test_engine) as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.action == "admin.login"))

        assert event is not None
        assert event.actor_id is not None
        assert event.actor_type == "doctor_admin"
        assert event.resource_id is not None
        assert event.trace_id is not None


def test_audit_action_filter(audit_client):
    response = audit_client.get("/admin/audit", params={"action": "admin.login"})
    assert response.status_code == 200
    assert "admin.login" in response.text


def test_audit_filter_validation(audit_client):
    response = audit_client.get(
        "/admin/audit", params={"action": "invalid action spaces"}
    )
    assert response.status_code == 400


def test_audit_has_no_delete_endpoint(audit_client):
    response = audit_client.delete("/admin/audit")
    assert response.status_code == 405


def test_request_contains_trace_id(audit_client):
    response = audit_client.get("/admin/audit")
    assert response.status_code == 200
    assert response.headers.get("X-Trace-ID")
