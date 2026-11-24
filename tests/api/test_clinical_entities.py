"""Phase 10 - Clinical entity API integration tests."""

import uuid

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
        ("health-issues", "Health Issues"),
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
        ("health-issues", "health_issue"),
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


def test_duplicate_returns_conflict(doctor_client):
    """Prevent duplicate subtype records."""

    concept_id = create_concept(doctor_client)

    create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    response = doctor_client.post(
        "/api/admin/health-issues",
        json={
            "concept_id": concept_id,
        },
    )

    assert response.status_code == 409


def test_wrong_kind_rejected(doctor_client):
    """Prevent symptom concepts from becoming health issues."""

    concept_id = create_concept(
        doctor_client,
        kind="symptom",
        name="Example Symptom",
    )

    response = doctor_client.post(
        "/api/admin/health-issues",
        json={
            "concept_id": concept_id,
        },
    )

    assert response.status_code == 422


def test_missing_concept(doctor_client):
    """Reject clinical records with nonexistent concepts."""

    response = doctor_client.post(
        "/api/admin/health-issues",
        json={
            "concept_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 404


# ==========================================
# AUTHENTICATION AND SECURITY TESTS
# ==========================================


def test_csrf_required(doctor_client):
    """Reject creation without a valid CSRF token."""

    concept_id = create_concept(doctor_client)

    response = doctor_client.post(
        "/api/admin/health-issues",
        json={
            "concept_id": concept_id,
        },
        headers={
            "X-CSRF-Token": "",
        },
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "section",
    [
        "health-issues",
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
# CONCEPT AUTOCOMPLETE TESTS
# ==========================================


def test_concept_autocomplete(doctor_client):
    """Verify autocomplete excludes already linked concepts."""

    concept_id = create_concept(
        doctor_client,
        name="Searchable Health Issue",
    )

    endpoint = "/api/admin/health-issues/concept-options"

    response = doctor_client.get(
        endpoint,
        params={
            "q": "searchable",
        },
    )

    assert response.status_code == 200

    ids = [item["id"] for item in response.json()]

    assert concept_id in ids

    create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    response = doctor_client.get(
        endpoint,
        params={
            "q": "searchable",
        },
    )

    assert response.status_code == 200
    assert response.json() == []


# ==========================================
# UPDATE AND DETAIL TESTS
# ==========================================


@pytest.mark.parametrize(
    ("section", "kind"),
    [
        ("health-issues", "health_issue"),
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
        ("health-issues", "health_issue"),
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


def test_review_requires_csrf(doctor_client):
    """Reject lifecycle operations without CSRF protection."""

    concept_id = create_concept(doctor_client)

    record = create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    response = doctor_client.post(
        f"/api/admin/health-issues/{concept_id}/submit",
        json={
            "version": record["version"],
        },
        headers={
            "X-CSRF-Token": "",
        },
    )

    assert response.status_code == 403


# ==========================================
# PHASE 9 TERMINOLOGY PROTECTION TESTS
# ==========================================


def test_linked_concept_rename_rejected(doctor_client):
    """Prevent unauthorized changes to linked canonical labels."""

    concept_id = create_concept(doctor_client)

    create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    response = doctor_client.put(
        f"/api/admin/concepts/{concept_id}",
        json={
            "kind": "health_issue",
            "namespace": "local",
            "canonical_name": "Changed Label",
            "status": "approved",
            "aliases": [],
        },
    )

    assert response.status_code == 422


def test_linked_concept_retirement_rejected(doctor_client):
    """Prevent retirement of concepts with active clinical records."""

    concept_id = create_concept(doctor_client)

    create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    response = doctor_client.delete(f"/api/admin/concepts/{concept_id}")

    assert response.status_code == 409


# ==========================================
# SEARCH AND FILTER TESTS
# ==========================================


def test_filter_clinical_records(doctor_client):
    """Verify clinical record search and status filtering."""

    concept_id = create_concept(
        doctor_client,
        name="Searchable Condition",
    )

    create_record(
        doctor_client,
        "health-issues",
        concept_id,
    )

    # Search by canonical name and draft status.
    response = doctor_client.get(
        "/api/admin/health-issues",
        params={
            "q": "searchable",
            "status": "draft",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1

    # Draft records must not appear in approved results.
    response = doctor_client.get(
        "/api/admin/health-issues",
        params={
            "status": "approved",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
