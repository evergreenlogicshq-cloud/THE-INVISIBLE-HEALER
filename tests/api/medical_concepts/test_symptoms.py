"""Phase 10 - Symptom API integration tests."""

import pytest

# ==========================================
# TEST HELPERS
# ==========================================


def create_concept(
    client,
    *,
    kind="health_issue",
    name="Example Health Issue",
    status="approved",
):
    """Create a medical concept for clinical entity testing."""

    response = client.post(
        "/api/admin/concepts",
        json={
            "kind": kind,
            "namespace": "local",
            "canonical_name": name,
            "status": status,
            "aliases": [],
        },
    )

    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_record(client, section, concept_id):
    """Create a draft clinical entity."""

    response = client.post(
        f"/api/admin/{section}",
        json={
            "concept_id": concept_id,
            "description": "Synthetic clinical record.",
        },
    )

    assert response.status_code == 201, response.text
    return response.json()


# ==========================================
# ADMIN PAGE TESTS
# ==========================================


@pytest.mark.parametrize(
    ("section", "title"),
    [
        ("symptoms", "Symptoms"),
    ],
)
def test_clinical_admin_pages(
    doctor_client,
    section,
    title,
):
    """Verify protected clinical admin pages render correctly."""

    response = doctor_client.get(f"/admin/{section}")

    assert response.status_code == 200
    assert title in response.text
    assert "Create Draft" in response.text
    assert "no-store" in response.headers["cache-control"]


# ==========================================
# CLINICAL ENTITY CREATION TESTS
# ==========================================


@pytest.mark.parametrize(
    ("section", "kind"),
    [
        ("symptoms", "symptom"),
    ],
)
def test_create_clinical_records(
    doctor_client,
    section,
    kind,
):
    """Verify health issues and symptoms can be created."""

    concept_id = create_concept(
        doctor_client,
        kind=kind,
    )

    result = create_record(
        doctor_client,
        section,
        concept_id,
    )

    assert result["concept_id"] == concept_id
    assert result["kind"] == kind
    assert result["status"] == "draft"
    assert result["version"] == 1


# ==========================================
# AUTHENTICATION AND SECURITY TESTS
# ==========================================


@pytest.mark.parametrize(
    "section",
    [
        "symptoms",
    ],
)
def test_disabled_auth_rejected(client, section):
    """Reject access when admin authentication is disabled."""

    response = client.get(f"/api/admin/{section}")

    assert response.status_code == 503


def test_unauthenticated_request(doctor_client):
    """Reject requests without an authenticated admin session."""

    doctor_client.cookies.clear()

    response = doctor_client.get("/api/admin/symptoms")

    assert response.status_code == 401


# ==========================================
# UPDATE AND DETAIL TESTS
# ==========================================


@pytest.mark.parametrize(
    ("section", "kind"),
    [
        ("symptoms", "symptom"),
    ],
)
def test_update_and_get_record(
    doctor_client,
    section,
    kind,
):
    """Verify draft updates and record retrieval."""

    concept_id = create_concept(
        doctor_client,
        kind=kind,
    )

    record = create_record(
        doctor_client,
        section,
        concept_id,
    )

    endpoint = f"/api/admin/{section}/{concept_id}"

    response = doctor_client.put(
        endpoint,
        json={
            "version": record["version"],
            "description": "Updated description.",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2

    response = doctor_client.get(endpoint)

    assert response.status_code == 200
    assert response.json()["description"] == "Updated description."


# ==========================================
# CLINICAL REVIEW AND LIFECYCLE TESTS
# ==========================================


@pytest.mark.parametrize(
    ("section", "kind"),
    [
        ("symptoms", "symptom"),
    ],
)
def test_review_and_retire(
    doctor_client,
    section,
    kind,
):
    """Verify the complete clinical entity lifecycle."""

    concept_id = create_concept(
        doctor_client,
        kind=kind,
    )

    record = create_record(
        doctor_client,
        section,
        concept_id,
    )

    endpoint = f"/api/admin/{section}/{concept_id}"

    # Step 1: Submit draft for clinical review.
    submitted = doctor_client.post(
        f"{endpoint}/submit",
        json={
            "version": record["version"],
        },
    )

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "in_review"

    # Step 2: Approve the reviewed clinical record.
    approved = doctor_client.post(
        f"{endpoint}/approve",
        json={
            "version": submitted.json()["version"],
            "notes": "Synthetic clinical review.",
        },
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    # Step 3: Soft-retire the approved record.
    retired = doctor_client.post(
        f"{endpoint}/retire",
        json={
            "version": approved.json()["version"],
        },
    )

    assert retired.status_code == 200, retired.text
    assert retired.json()["status"] == "retired"
