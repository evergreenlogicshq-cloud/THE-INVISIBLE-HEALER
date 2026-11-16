"""
The Invisible Healer
Phase 05 - Admin Interface Tests

Acceptance requirements:
    1. GET /admin responds successfully.
    2. HTML is server-rendered by Jinja2.
    3. Base layout and navigation are present.
    4. Static CSS and JavaScript are served.
    5. Flash feedback works.
    6. Untrusted input is not reflected.
    7. Dashboard contains no live clinical data.
    8. No Admin mutation endpoint is exposed.
    9. Existing health endpoints remain available.
"""

from fastapi.testclient import TestClient


def test_admin_dashboard_returns_200(client: TestClient) -> None:
    response = client.get("/admin")
    assert response.status_code == 200


def test_admin_dashboard_returns_html(client: TestClient) -> None:
    response = client.get("/admin")
    content_type = response.headers["content-type"]
    assert content_type.startswith("text/html")


def test_admin_dashboard_contains_title(client: TestClient) -> None:
    response = client.get("/admin")
    assert "Dashboard" in response.text
    assert "The Invisible Healer" in response.text


def test_admin_template_is_rendered(client: TestClient) -> None:
    response = client.get("/admin")
    assert "{{" not in response.text
    assert "{%" not in response.text
    assert 'id="main-content"' in response.text


def test_admin_has_semantic_navigation(client: TestClient) -> None:
    response = client.get("/admin")
    assert "<nav" in response.text
    assert 'aria-label="Primary navigation"' in response.text
    assert 'aria-current="page"' in response.text


def test_admin_has_skip_navigation(client: TestClient) -> None:
    response = client.get("/admin")
    assert "Skip to main content" in response.text
    assert 'href="#main-content"' in response.text


def test_admin_has_responsive_viewport(client: TestClient) -> None:
    response = client.get("/admin")
    assert 'name="viewport"' in response.text


def test_admin_displays_planned_modules(client: TestClient) -> None:
    response = client.get("/admin")

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


def test_admin_displays_security_notice(client: TestClient) -> None:
    response = client.get("/admin")
    assert "Administration shell preview" in response.text
    assert "Authentication" in response.text


def test_admin_displays_next_phase(client: TestClient) -> None:
    response = client.get("/admin")
    assert "Phase 06" in response.text
    assert "Secure Sessions" in response.text


def test_admin_css_is_available(client: TestClient) -> None:
    response = client.get("/static/css/admin.css")
    assert response.status_code == 200
    assert "--color-primary" in response.text
    assert ".admin-layout" in response.text


def test_admin_javascript_is_available(client: TestClient) -> None:
    response = client.get("/static/js/admin.js")
    assert response.status_code == 200
    assert "initializeSidebar" in response.text
    assert "initializeNotifications" in response.text


def test_admin_references_static_assets(client: TestClient) -> None:
    response = client.get("/admin")
    assert "/static/css/admin.css" in response.text
    assert "/static/js/admin.js" in response.text


def test_missing_static_asset_returns_404(client: TestClient) -> None:
    response = client.get("/static/css/missing.css")
    assert response.status_code == 404


def test_admin_welcome_flash(client: TestClient) -> None:
    response = client.get("/admin?notice=welcome")
    assert response.status_code == 200
    assert "Welcome to the Admin dashboard." in response.text
    assert "alert-success" in response.text


def test_admin_unknown_flash_is_ignored(client: TestClient) -> None:
    response = client.get("/admin?notice=unknown")
    assert response.status_code == 200
    assert "data-dismissible-alert" not in response.text


def test_admin_does_not_reflect_untrusted_notice(client: TestClient) -> None:
    payload = "<script>alert(1)</script>"
    response = client.get("/admin", params={"notice": payload})
    assert response.status_code == 200
    assert payload not in response.text
    assert "alert-success" not in response.text


def test_admin_has_csrf_integration_placeholder(client: TestClient) -> None:
    response = client.get("/admin")
    assert 'name="admin-csrf-token"' in response.text
    # A blank placeholder must not be treated
    # as a real, verified CSRF token.
    assert 'content=""' in response.text


def test_admin_rejects_post_without_route(client: TestClient) -> None:
    response = client.post("/admin", data={"example": "value"})
    assert response.status_code == 405


def test_admin_has_no_login_endpoint_yet(client: TestClient) -> None:
    response = client.get("/admin/login")
    assert response.status_code == 404


def test_health_live_still_works(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_admin_route_is_registered_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/admin" in paths
    assert "/health/live" in paths
    assert "/health/ready" in paths
