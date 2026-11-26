"""Phase 11 catalog API behavior and access control."""

import pytest

from tests.api.medical_concepts.test_health_issues import create_concept

CASES = [("products", "product"), ("remedies", "remedy"), ("ingredients", "ingredient")]


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_catalog_access_requires_authentication(doctor_client, section, kind):
    doctor_client.cookies.clear()
    assert doctor_client.get(f"/admin/{section}").status_code == 401
    assert doctor_client.get(f"/api/admin/{section}").status_code == 401


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_catalog_lifecycle(doctor_client, section, kind):
    client = doctor_client
    base = f"/api/admin/{section}"
    page = client.get(f"/admin/{section}?status=")
    assert page.status_code == 200
    assert "Create Draft" in page.text
    concept_id = create_concept(client, kind=kind, name=f"Example {kind}")
    assert (
        len(client.get(f"{base}/concept-options", params={"q": "example"}).json()) == 1
    )
    payload = {
        "concept_id": concept_id,
        "description": "Example description",
        "source_reference": "Synthetic source",
    }
    response = client.post(base, json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["status"] == "draft" and record["version"] == 1
    assert client.post(base, json=payload).status_code == 409
    assert client.get(f"{base}/concept-options", params={"q": "example"}).json() == []
    assert (
        client.get(base, params={"q": "example", "page_size": 1}).json()["total"] == 1
    )
    assert client.get(f"{base}/{concept_id}").json()["kind"] == kind
    assert (
        client.post(f"{base}/{concept_id}/submit", json={"version": 1}).json()["status"]
        == "in_review"
    )
    assert (
        client.post(
            f"{base}/{concept_id}/approve", json={"version": 1, "notes": "reviewed"}
        ).status_code
        == 409
    )
    assert (
        client.post(f"{base}/{concept_id}/approve", json={"version": 2}).status_code
        == 422
    )
    assert (
        client.post(
            f"{base}/{concept_id}/reject", json={"version": 2, "notes": "revise"}
        ).json()["status"]
        == "draft"
    )
    updated = client.put(
        f"{base}/{concept_id}",
        json={"version": 3, "description": "Updated", "source_reference": "Source"},
    )
    assert updated.status_code == 200, updated.text
    assert (
        client.post(f"{base}/{concept_id}/submit", json={"version": 4}).status_code
        == 200
    )
    approved = client.post(
        f"{base}/{concept_id}/approve", json={"version": 5, "notes": "Reviewed"}
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert (
        client.delete(f"{base}/{concept_id}", params={"version": 6}).json()["status"]
        == "retired"
    )
    assert client.put(f"{base}/{concept_id}", json={"version": 7}).status_code == 409


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_catalog_validation_and_csrf(doctor_client, section, kind):
    client = doctor_client
    base = f"/api/admin/{section}"
    concept_id = create_concept(client, kind=kind, name=f"Test {kind}")
    payload = {"concept_id": concept_id, "description": "Example"}
    assert (
        client.post(base, json=payload, headers={"X-CSRF-Token": "invalid"}).status_code
        == 403
    )
    assert client.post(base, json={**payload, "unexpected": True}).status_code == 422
    assert client.post(base, json=payload).status_code == 201
    assert (
        client.post(f"{base}/{concept_id}/submit", json={"version": 1}).status_code
        == 422
    )
    assert client.delete(f"/api/admin/concepts/{concept_id}").status_code == 409


def test_ingredient_reference_validation(doctor_client):
    concept_id = create_concept(
        doctor_client, kind="ingredient", name="Test ingredient"
    )
    base = {
        "concept_id": concept_id,
        "description": "Ingredient",
        "source_reference": "Source",
    }
    for fields in (
        {"reference_amount": "1"},
        {
            "reference_amount": "0",
            "reference_unit": "mg",
            "reference_basis": "per serving",
        },
        {
            "reference_amount": "1",
            "reference_unit": "bad",
            "reference_basis": "serving",
        },
    ):
        assert (
            doctor_client.post(
                "/api/admin/ingredients", json={**base, **fields}
            ).status_code
            == 422
        )
    response = doctor_client.post(
        "/api/admin/ingredients",
        json={
            **base,
            "reference_amount": "1.250001",
            "reference_unit": "mg",
            "reference_basis": "per serving",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["reference_amount"] == "1.250001"


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_parent_concept_review_and_terminology_protection(doctor_client, section, kind):
    client = doctor_client
    base = f"/api/admin/{section}"
    name = f"Draft {kind}"
    concept_id = create_concept(client, kind=kind, name=name, status="draft")
    assert (
        client.post(
            base,
            json={
                "concept_id": concept_id,
                "description": "Description",
                "source_reference": "Source",
            },
        ).status_code
        == 201
    )
    assert (
        client.post(f"{base}/{concept_id}/submit", json={"version": 1}).status_code
        == 200
    )
    assert (
        client.post(
            f"{base}/{concept_id}/approve", json={"version": 2, "notes": "Reviewed"}
        ).status_code
        == 409
    )
    concept_data = {
        "kind": kind,
        "namespace": "local",
        "canonical_name": name,
        "status": "approved",
        "aliases": [],
    }
    assert (
        client.put(
            f"/api/admin/concepts/{concept_id}",
            json={**concept_data, "canonical_name": "Changed"},
        ).status_code
        == 422
    )
    assert (
        client.put(f"/api/admin/concepts/{concept_id}", json=concept_data).status_code
        == 200
    )
    assert (
        client.post(
            f"{base}/{concept_id}/approve", json={"version": 2, "notes": "Reviewed"}
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/admin/concepts/{concept_id}",
            json={**concept_data, "status": "draft"},
        ).status_code
        == 422
    )
    assert client.delete(f"/api/admin/concepts/{concept_id}").status_code == 409


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_catalog_search_status_and_pagination(doctor_client, section, kind):
    client = doctor_client
    base = f"/api/admin/{section}"
    for index in range(3):
        name = f"Unique {kind} {index}"
        concept = client.post(
            "/api/admin/concepts",
            json={
                "kind": kind,
                "namespace": "local",
                "canonical_name": name,
                "status": "approved",
                "aliases": [f"Alias {kind} {index}"],
            },
        )
        assert concept.status_code == 201
        result = client.post(
            base,
            json={
                "concept_id": concept.json()["id"],
                "description": "Description",
                "source_reference": "Source",
            },
        )
        assert result.status_code == 201
    first = client.get(
        base, params={"page": 1, "page_size": 1, "status": "draft"}
    ).json()
    second = client.get(
        base, params={"page": 2, "page_size": 1, "status": "draft"}
    ).json()
    assert first["total"] == second["total"] == 3
    assert first["items"][0]["concept_id"] != second["items"][0]["concept_id"]
    assert client.get(base, params={"status": "approved"}).json()["total"] == 0
    assert client.get(base, params={"q": f"Alias {kind} 2"}).json()["total"] == 1
    assert (
        client.get(f"/admin/{section}", params={"q": "Unique", "page": 1}).status_code
        == 200
    )


@pytest.mark.parametrize(("section", "kind"), CASES)
def test_all_catalog_writes_require_csrf(doctor_client, section, kind):
    client = doctor_client
    base = f"/api/admin/{section}"
    concept_id = create_concept(client, kind=kind, name=f"CSRF {kind}")
    assert (
        client.post(
            base,
            json={
                "concept_id": concept_id,
                "description": "Description",
                "source_reference": "Source",
            },
        ).status_code
        == 201
    )
    headers = {"X-CSRF-Token": "invalid"}
    assert (
        client.put(
            f"{base}/{concept_id}", json={"version": 1}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"{base}/{concept_id}/submit", json={"version": 1}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"{base}/{concept_id}", params={"version": 1}, headers=headers
        ).status_code
        == 403
    )
    assert client.get(f"{base}/{concept_id}").json()["version"] == 1


@pytest.mark.parametrize(
    ("section", "kind", "metadata"),
    [
        (
            "products",
            "product",
            {
                "manufacturer": "Example manufacturer",
                "brand": "Example brand",
                "dosage_form": "Capsule",
                "product_category": "Supplement",
                "country_of_origin": "Canada",
                "regulatory_number": "EXAMPLE",
            },
        ),
        (
            "remedies",
            "remedy",
            {
                "remedy_type": "Preparation",
                "preparation": "Synthetic preparation",
                "administration_route": "Oral",
                "limitations": "Synthetic limitations",
            },
        ),
        (
            "ingredients",
            "ingredient",
            {
                "scientific_name": "Example species",
                "ingredient_type": "Botanical",
                "source_part": "Leaf",
                "reference_amount": "1.234567",
                "reference_unit": "mg",
                "reference_basis": "per serving",
            },
        ),
    ],
)
def test_catalog_metadata_round_trip(doctor_client, section, kind, metadata):
    base = f"/api/admin/{section}"
    concept_id = create_concept(doctor_client, kind=kind, name=f"Metadata {kind}")
    values = {
        "description": "Synthetic",
        "source_reference": "Label",
        "evidence_notes": "Unverified notes",
        **metadata,
    }
    response = doctor_client.post(base, json={"concept_id": concept_id, **values})
    assert response.status_code == 201, response.text
    result = doctor_client.get(f"{base}/{concept_id}").json()
    for field, value in values.items():
        assert result[field] == value
    response = doctor_client.put(f"{base}/{concept_id}", json={"version": 1, **values})
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2
    for field, value in values.items():
        assert response.json()[field] == value
