"""Phase 09 - Medical concept API integration tests."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin.audit import AuditEvent
from app.models.admin.concept import MedicalConcept


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
