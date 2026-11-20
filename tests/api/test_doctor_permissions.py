"""
Phase 07 - Single Doctor Admin Tests.

Covers:
    - Single Doctor Admin type
    - Full administrative capabilities
    - Unauthenticated access denied
    - Authenticated access allowed
    - Inactive accounts denied
    - No role assignment endpoint
    - No unauthorized account creation endpoint
    - No roles or permissions tables
    - Existing health endpoints remain available
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.permissions import ADMIN_TYPE, DOCTOR_CAPABILITIES
from app.db.base import Base
from app.models.admin.admin_user import AdminUser
from app.services.admin.auth import (
    SESSION_COOKIE_NAME,
    create_admin_session,
    create_admin_user,
)

TEST_EMAIL = "doctor-phase7@example.com"
TEST_PASSWORD = "Doctor-Phase7-Password-2026!"


@pytest.fixture
def doctor_client(
    app: FastAPI,
    test_engine: Engine,
    test_settings: Settings,
) -> Generator[TestClient, None, None]:
    """
    Configure an isolated authenticated Doctor Admin.

    Uses real Phase 06 session issuance.
    No mock authorization is used.
    """

    test_settings.ADMIN_SESSIONS_ENABLED = True
    test_settings.SESSION_SECRET = SecretStr(
        "doctor-phase7-test-secret-at-least-32-chars"
    )
    test_settings.SESSION_COOKIE_SECURE = False
    test_settings.SESSION_MAX_AGE_SECONDS = 3600
    test_settings.SESSION_IDLE_TIMEOUT_SECONDS = 900

    Base.metadata.create_all(bind=test_engine)

    try:
        with Session(test_engine) as db:
            user = create_admin_user(
                db,
                email=TEST_EMAIL,
                full_name="Test Doctor",
                password=TEST_PASSWORD,
            )

            created = create_admin_session(db, user, test_settings)
            cookie_value = created.cookie_value
            db.commit()

        with TestClient(app) as client:
            client.cookies.set(SESSION_COOKIE_NAME, cookie_value)
            yield client

    finally:
        Base.metadata.drop_all(bind=test_engine)


def test_single_administrator_type():
    assert ADMIN_TYPE == "doctor"


def test_doctor_has_administrative_capabilities():
    expected = {
        "manage_medical_concepts",
        "manage_health_issues",
        "manage_symptoms",
        "manage_clinical_documents",
        "publish_clinical_documents",
        "manage_clinical_protocols",
        "manage_safety_rules",
        "manage_training_data",
        "manage_evaluation_data",
        "view_audit_records",
    }

    assert expected.issubset(set(DOCTOR_CAPABILITIES))


def test_no_roles_or_permissions_tables():
    """
    Only Phase 06 authentication tables exist.

    Phase 07 does not introduce an unnecessary
    role-based database schema.
    """
    assert set(Base.metadata.tables) == {
        "admin_users",
        "admin_sessions",
        "admin_login_attempts",
        "audit_events",
    }


def test_unauthenticated_users_cannot_view_directory(client: TestClient):
    response = client.get("/admin/users")
    # Default test settings disable authentication.
    assert response.status_code == 503


def test_missing_session_returns_401(doctor_client: TestClient):
    doctor_client.cookies.clear()
    response = doctor_client.get("/admin/users")
    assert response.status_code == 401


def test_authenticated_doctor_can_view_directory(doctor_client: TestClient):
    response = doctor_client.get("/admin/users")
    assert response.status_code == 200
    assert "Doctor Administrators" in response.text
    assert TEST_EMAIL in response.text
    assert "Test Doctor" in response.text


def test_doctor_directory_contains_single_type(doctor_client: TestClient):
    response = doctor_client.get("/admin/users")
    assert response.status_code == 200
    assert "Doctor Admin" in response.text


def test_doctor_directory_is_not_cached(doctor_client: TestClient):
    response = doctor_client.get("/admin/users")
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]


def test_directory_does_not_disclose_secrets(doctor_client: TestClient):
    response = doctor_client.get("/admin/users")
    assert response.status_code == 200
    assert TEST_PASSWORD not in response.text
    assert "password_hash" not in response.text
    assert "csrf_secret" not in response.text
    assert "token_hash" not in response.text


def test_inactive_doctor_cannot_access_directory(
    doctor_client: TestClient, test_engine: Engine
):
    """
    Disable the administrator after a session
    has already been issued.

    The next request must be rejected.
    """

    with Session(test_engine) as db:
        user = db.scalar(select(AdminUser).where(AdminUser.email == TEST_EMAIL))

        assert user is not None
        user.is_active = False
        db.commit()

    response = doctor_client.get("/admin/users")
    assert response.status_code == 401


def test_role_assignment_route_does_not_exist(doctor_client: TestClient):
    """
    Doctor Admin users do not need
    role assignments.
    """

    response = doctor_client.post(
        "/admin/users/123/roles",
        json={"roles": ["publisher"]},
    )

    assert response.status_code == 404


def test_directory_does_not_allow_user_creation(doctor_client: TestClient):
    response = doctor_client.post(
        "/admin/users",
        json={
            "email": "new@example.com",
            "full_name": "New Doctor",
        },
    )

    assert response.status_code == 405


def test_health_endpoint_still_available(doctor_client: TestClient):
    response = doctor_client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_users_route_registered(doctor_client: TestClient):
    response = doctor_client.get("/openapi.json")
    assert response.status_code == 200
    assert "/admin/users" in response.json()["paths"]
