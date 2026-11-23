"""Phase 09 - Medical concept API integration tests."""

import re
import uuid
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
from app.models.admin.concept import MedicalConcept
from app.services.admin.auth import create_admin_user

EMAIL = "concept-doctor@example.com"
PASSWORD = "Concept-Doctor-Password-2026!"


def extract_csrf_token(html: str) -> str:
    match = re.search(
        r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']',
        html,
    )
    assert match is not None, "CSRF token not found in HTML."
    return match.group(1)


@pytest.fixture
def doctor_client(
    app: FastAPI, test_engine: Engine, test_settings: Settings
) -> Generator[TestClient, None, None]:
    test_settings.ADMIN_SESSIONS_ENABLED = True
    test_settings.SESSION_SECRET = SecretStr(
        "concept-test-session-secret-at-least-32-characters"
    )
    test_settings.SESSION_COOKIE_SECURE = False
    test_settings.SESSION_MAX_AGE_SECONDS = 3600
    test_settings.SESSION_IDLE_TIMEOUT_SECONDS = 900

    registered_routes = set(app.openapi().get("paths", {}))
    assert "/admin/concepts" in registered_routes, (
        "Phase 09 admin router is not registered in the test application."
    )
    assert "/api/admin/concepts" in registered_routes, (
        "Phase 09 API router is not registered in the test application."
    )

    Base.metadata.create_all(test_engine)

    try:
        with Session(test_engine) as db:
            create_admin_user(
                db,
                email=EMAIL,
                full_name="Concept Test Doctor",
                password=PASSWORD,
            )
            db.commit()

        with TestClient(app) as client:
            login_page = client.get("/admin/login")
            assert login_page.status_code == 200

            csrf_token = extract_csrf_token(login_page.text)

            response = client.post(
                "/admin/login",
                data={
                    "email": EMAIL,
                    "password": PASSWORD,
                    "csrf_token": csrf_token,
                },
                follow_redirects=False,
            )
            assert response.status_code == 303
            admin_page = client.get("/admin/concepts")
            assert admin_page.status_code == 200
            csrf_token = extract_csrf_token(admin_page.text)
            client.headers.update({"X-CSRF-Token": csrf_token})

            yield client

    finally:
        Base.metadata.drop_all(test_engine)


def concept_data(name="Headache"):
    return {
        "kind": "symptom",
        "namespace": "local",
        "canonical_name": name,
        "ontology_code": None,
        "status": "draft",
        "aliases": ["Head Pain"],
    }


def test_unauthenticated_concept_api(client):
    response = client.get("/api/admin/concepts")
    assert response.status_code == 503


def test_admin_page(doctor_client):
    response = doctor_client.get("/admin/concepts")
    assert response.status_code == 200
    assert "Medical Concepts" in response.text
    assert "Create Medical Concept" in response.text
    assert "no-store" in response.headers["cache-control"]


def test_create_concept_api(doctor_client):
    response = doctor_client.post("/api/admin/concepts", json=concept_data())
    assert response.status_code == 201
    result = response.json()
    assert result["canonical_name"] == "Headache"
    assert result["normalized_name"] == "headache"
    assert result["status"] == "draft"
    assert "Head Pain" in result["aliases"]


def test_create_requires_csrf(doctor_client):
    response = doctor_client.post(
        "/api/admin/concepts",
        json=concept_data(),
        headers={"X-CSRF-Token": ""},
    )
    assert response.status_code == 403


def test_duplicate_api_returns_conflict(doctor_client):
    first = doctor_client.post("/api/admin/concepts", json=concept_data("Headache"))
    assert first.status_code == 201
    second_data = concept_data("HEADACHE")
    second_data["aliases"] = []
    duplicate = doctor_client.post("/api/admin/concepts", json=second_data)
    assert duplicate.status_code == 409


def test_list_and_search(doctor_client):
    created = doctor_client.post("/api/admin/concepts", json=concept_data())
    assert created.status_code == 201
    response = doctor_client.get("/api/admin/concepts", params={"q": "head pain"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1


def test_update_concept(doctor_client):
    created = doctor_client.post("/api/admin/concepts", json=concept_data())
    assert created.status_code == 201
    concept_id = created.json()["id"]
    data = concept_data("Headache Disorder")
    data["aliases"] = ["Cephalalgia"]
    response = doctor_client.put(f"/api/admin/concepts/{concept_id}", json=data)
    assert response.status_code == 200
    assert response.json()["id"] == concept_id
    assert response.json()["canonical_name"] == "Headache Disorder"


def test_retire_concept(doctor_client, test_engine):
    created = doctor_client.post("/api/admin/concepts", json=concept_data())
    assert created.status_code == 201
    concept_id = created.json()["id"]
    response = doctor_client.delete(f"/api/admin/concepts/{concept_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "retired"

    with Session(test_engine) as db:
        persisted = db.scalar(
            select(MedicalConcept).where(MedicalConcept.normalized_name == "headache")
        )

        assert persisted is not None
        assert persisted.status == "retired"


def test_create_audit_event(doctor_client, test_engine):
    response = doctor_client.post("/api/admin/concepts", json=concept_data())
    assert response.status_code == 201

    with Session(test_engine) as db:
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.action == "medical_concept.create")
        ).all()

        assert len(events) == 1
        assert events[0].actor_id is not None
        assert events[0].decision == "allowed"


def test_invalid_kind_is_rejected(doctor_client):
    data = concept_data()
    data["kind"] = "unknown"
    response = doctor_client.post("/api/admin/concepts", json=data)
    assert response.status_code == 422


def test_missing_concept_returns_404(doctor_client):
    response = doctor_client.get(f"/api/admin/concepts/{uuid.uuid4()}")
    assert response.status_code == 404
