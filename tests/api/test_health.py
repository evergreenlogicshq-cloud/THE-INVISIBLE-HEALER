"""
The Invisible Healer
Health Endpoint Tests

Phase 03 Acceptance Tests

Test scenarios:
    - Liveness works.
    - Readiness checks the database.
    - Ready database returns HTTP 200.
    - Unavailable database returns HTTP 503.
    - DB errors do not leak credentials.
    - OpenAPI remains available in testing.
    - Unknown routes use existing error handling.
"""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

# ============================================
# LIVENESS TEST
# ============================================


def test_liveness_endpoint(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "The Invisible Healer"


# ============================================
# DATABASE READINESS TEST
# ============================================


def test_readiness_endpoint(client: TestClient):
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["configuration"] == "ok"
    assert data["checks"]["database"] == "ok"


# ============================================
# DATABASE UNAVAILABLE TEST
# ============================================


def test_readiness_database_failure(client: TestClient):
    """
    A DB failure must return HTTP 503.
    """

    with patch(
        "app.api.routes.health.check_database_connection",
        side_effect=OperationalError(
            "SELECT 1",
            {},
            Exception("Simulated database failure"),
        ),
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["checks"]["database"] == "unavailable"
    assert "Simulated database failure" not in response.text


# ============================================
# NEGATIVE DATABASE RESULT
# ============================================


def test_readiness_false_connection_result(client: TestClient):
    """
    A failed connectivity result must
    not be reported as ready.
    """

    with patch(
        "app.api.routes.health.check_database_connection",
        return_value=False,
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


# ============================================
# LIVENESS INDEPENDENCE TEST
# ============================================


def test_liveness_when_database_fails(client: TestClient):
    """
    Liveness must not depend on PostgreSQL.
    """

    with patch(
        "app.api.routes.health.check_database_connection",
        side_effect=Exception("Database unavailable"),
    ):
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


# ============================================
# OPENAPI TEST
# ============================================


def test_openapi_schema_available(client: TestClient):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health/live" in paths
    assert "/health/ready" in paths


# ============================================
# UNKNOWN ROUTE TEST
# ============================================


def test_unknown_endpoint_returns_404(client: TestClient):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "HTTP_ERROR"


# ============================================
# LIVENESS RESPONSE CONTRACT
# ============================================


def test_liveness_has_response_contract(client: TestClient):
    response = client.get("/health/live")
    data = response.json()
    assert set(data.keys()) == {"status", "service"}
