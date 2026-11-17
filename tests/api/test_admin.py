"""
The Invisible Healer
Phases 05-06 - Admin Dashboard Tests

Responsibilities:
    - Verify authenticated dashboard access.
    - Verify server-rendered Jinja2 HTML.
    - Verify navigation and accessibility.
    - Verify static assets.
    - Verify flash notifications.
    - Verify active CSRF integration.
    - Prevent untrusted content reflection.
    - Preserve health endpoints.

All database operations use isolated SQLite.
No live Supabase connection is required.
"""

import re
from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.base import Base
from app.services.admin.auth import create_admin_user

TEST_EMAIL = "dashboard-admin@example.com"
TEST_PASSWORD = "Dashboard-test-password-2026!"


# ============================================
# AUTHENTICATED TEST CLIENT
# ============================================


@pytest.fixture
def authenticated_client(
    app: FastAPI,
    test_engine: Engine,
    test_settings: Settings,
) -> Generator[TestClient, None, None]:
    """
    Provide an authenticated Admin test client.

    Uses the actual login endpoint and server-side
    session implementation from Phase 06.
    """

    # Enable authentication for this isolated test.
    test_settings.ADMIN_SESSIONS_ENABLED = True
    test_settings.SESSION_SECRET = SecretStr(
        "dashboard-test-secret-of-at-least-32-characters"
    )
    test_settings.SESSION_COOKIE_SECURE = False
    test_settings.SESSION_COOKIE_HTTPONLY = True
    test_settings.SESSION_COOKIE_SAMESITE = "lax"
    test_settings.SESSION_MAX_AGE_SECONDS = 3600
    test_settings.SESSION_IDLE_TIMEOUT_SECONDS = 900
    assert app.state.settings is test_settings
    # Create only the registered test tables.
    Base.metadata.create_all(bind=test_engine)

    try:
        # Provision a test-only administrator.
        with Session(test_engine) as db:
            create_admin_user(
                db,
                email=TEST_EMAIL,
                full_name="Dashboard Test Admin",
                password=TEST_PASSWORD,
            )

            db.commit()

        with TestClient(app) as client:
            # GET login page to receive login CSRF.
            login_page = client.get("/admin/login")
            assert login_page.status_code == 200
            csrf_match = re.search(
                r'name="csrf_token"\s+value="([^"]+)"', login_page.text
            )
            assert csrf_match is not None

            # Authenticate through the actual API.
            login_response = client.post(
                "/admin/login",
                data={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "csrf_token": csrf_match.group(1),
                },
                follow_redirects=False,
            )

            assert login_response.status_code == 303

            # All dashboard tests use this logged-in client.
            yield client

    finally:
        Base.metadata.drop_all(bind=test_engine)


# ============================================
# DASHBOARD ACCESS
# ============================================


def test_admin_dashboard_returns_200(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200


def test_admin_dashboard_returns_html(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_admin_dashboard_contains_title(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "The Invisible Healer" in response.text


# ============================================
# JINJA2 TEMPLATE RENDERING
# ============================================


def test_admin_template_is_rendered(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "{{" not in response.text
    assert "{%" not in response.text
    assert 'id="main-content"' in response.text


# ============================================
# NAVIGATION AND ACCESSIBILITY
# ============================================


def test_admin_has_semantic_navigation(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "<nav" in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert 'aria-current="page"' in response.text


def test_admin_has_skip_navigation(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "Skip to main content" in response.text
    assert 'href="#main-content"' in response.text


def test_admin_has_responsive_viewport(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert 'name="viewport"' in response.text


# ============================================
# KNOWLEDGE MODULES
# ============================================


def test_admin_displays_planned_modules(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200

    expected_modules = (
        "Medical Concepts",
        "Health Issues",
        "Products &amp; Remedies",
        "Clinical Documents",
        "Clinical Protocols",
        "Training &amp; Evaluation",
    )

    for module in expected_modules:
        assert module in response.text


# ============================================
# PHASE 06 SECURITY STATUS
# ============================================


def test_admin_displays_security_notice(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "Protected Administration Workspace" in response.text
    assert "authentication" in response.text.lower()
    assert "CSRF" in response.text


def test_admin_displays_next_phase(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "Phase 07" in response.text
    assert "Role-Based Permissions" in response.text


# ============================================
# STATIC ASSETS
# ============================================


def test_admin_css_is_available(
    client: TestClient,
) -> None:
    response = client.get("/static/css/admin.css")
    assert response.status_code == 200
    assert "--color-primary" in response.text
    assert ".admin-layout" in response.text


def test_admin_javascript_is_available(client: TestClient) -> None:
    response = client.get("/static/js/admin.js")
    assert response.status_code == 200
    assert "initializeSidebar" in response.text
    assert "initializeNotifications" in response.text


def test_admin_references_static_assets(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert "/static/css/admin.css" in response.text
    assert "/static/js/admin.js" in response.text


def test_missing_static_asset_returns_404(client: TestClient) -> None:
    response = client.get("/static/css/missing.css")
    assert response.status_code == 404


# ============================================
# FLASH NOTIFICATIONS
# ============================================


def test_admin_welcome_flash(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin?notice=welcome")
    assert response.status_code == 200
    assert "Welcome to the Admin dashboard." in response.text
    assert "alert-success" in response.text


def test_admin_unknown_flash_is_ignored(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin?notice=unknown")
    assert response.status_code == 200
    assert "data-dismissible-alert" not in response.text


def test_admin_does_not_reflect_untrusted_notice(
    authenticated_client: TestClient,
) -> None:
    payload = "<script>alert(1)</script>"
    response = authenticated_client.get("/admin", params={"notice": payload})
    assert response.status_code == 200
    assert payload not in response.text
    assert "alert-success" not in response.text


# ============================================
# ACTIVE CSRF INTEGRATION
# ============================================


def test_admin_has_active_csrf_token(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/admin")
    assert response.status_code == 200
    assert 'name="admin-csrf-token"' in response.text
    csrf_match = re.search(
        r'name="admin-csrf-token"\s+'
        r'content="([^"]+)"',
        response.text,
    )
    assert csrf_match is not None
    csrf_token = csrf_match.group(1)
    # Phase 06 must supply a real nonempty token.
    assert len(csrf_token) >= 32
    # The logout form must carry a matching token.
    logout_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)

    assert logout_match is not None
    assert logout_match.group(1) == csrf_token


# ============================================
# UNSUPPORTED WRITE ROUTES
# ============================================


def test_admin_rejects_post_without_route(client: TestClient) -> None:
    response = client.post("/admin", data={"example": "value"})
    assert response.status_code == 405


# ============================================
# LOGIN ENDPOINT
# ============================================


def test_admin_login_endpoint_exists(
    authenticated_client: TestClient,
) -> None:
    # Already authenticated clients are redirected
    # away from the login page.
    response = authenticated_client.get("/admin/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


# ============================================
# HEALTH ENDPOINT REGRESSION
# ============================================


def test_health_live_still_works(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


# ============================================
# OPENAPI ROUTE REGISTRATION
# ============================================


def test_admin_route_is_registered_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/admin" in paths
    assert "/admin/login" in paths
    assert "/admin/logout" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
