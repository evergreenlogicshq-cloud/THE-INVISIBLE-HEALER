
"""
Phase 01 - Health API Tests

Acceptance requirements:
    - Liveness endpoint returns HTTP 200.
    - Readiness endpoint returns HTTP 200.
    - Readiness includes configuration status.
    - No database connection is attempted.
    - API documentation is available in testing.
    - Unknown API routes return structured 404.
"""

from fastapi.testclient import TestClient


def test_liveness_endpoint(client: TestClient):
    """
    Verify application liveness.
    """

    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == ("The Invisible Healer")


def test_readiness_endpoint(client: TestClient):
    """
    Verify application readiness.
    """

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["configuration"] == "ok"


def test_readiness_does_not_claim_database_check(client: TestClient):
    """
    Phase 01 readiness must not claim that
    PostgreSQL connectivity was checked.
    """

    response = client.get("/health/ready")
    checks = response.json()["checks"]
    assert "database" not in checks


def test_openapi_schema_available(client: TestClient):
    """
    Verify Swagger OpenAPI schema generation.
    """

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "/health/live" in data["paths"]
    assert "/health/ready" in data["paths"]


def test_unknown_endpoint_returns_404(client: TestClient):
    """
    Verify centralized HTTP error handling.
    """

    response = client.get("/does-not-exist")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "HTTP_ERROR"


def test_liveness_has_response_contract(client: TestClient):
    """
    Verify liveness response schema.
    """

    response = client.get("/health/live")
    data = response.json()
    assert set(data.keys()) == {"status", "service"}
