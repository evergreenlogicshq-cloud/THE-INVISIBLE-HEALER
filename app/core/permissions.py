"""
Phase 07 - Single Doctor Admin Authorization.

The Invisible Healer has one type of administrator:
Doctor Admin.

All active, authenticated administrator accounts have
full access to administrative functionality.

No role hierarchy or permissions database is required.
"""

from typing import Annotated, Final

from fastapi import Depends, HTTPException, status

from app.api.dependencies import require_admin
from app.services.admin.auth import AuthenticatedAdmin

ADMIN_TYPE: Final[str] = "doctor"

DOCTOR_CAPABILITIES: Final[tuple[str, ...]] = (
    "manage_admin_users",
    "manage_medical_concepts",
    "manage_health_issues",
    "manage_symptoms",
    "manage_products",
    "manage_remedies",
    "manage_ingredients",
    "manage_relationships",
    "manage_clinical_documents",
    "review_clinical_documents",
    "publish_clinical_documents",
    "manage_clinical_protocols",
    "manage_safety_rules",
    "manage_training_data",
    "manage_evaluation_data",
    "view_audit_records",
    "manage_system_operations",
)


def require_doctor_admin(
    authenticated: Annotated[AuthenticatedAdmin, Depends(require_admin)],
) -> AuthenticatedAdmin:
    """
    Require an authenticated and active Doctor Admin.

    Phase 06 validates:
      - Signed session cookie
      - Session existence and revocation
      - Session expiry
      - Idle timeout
      - Active administrator account

    Phase 07 uses a single administrator type.

    IMPORTANT:
    Only trusted administrators who are actually
    authorized doctors should be provisioned.
    """

    user = authenticated.user

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor administrator account is inactive",
        )

    return authenticated


DoctorAdminDependency = Annotated[AuthenticatedAdmin, Depends(require_doctor_admin)]


def get_doctor_capabilities() -> tuple[str, ...]:
    """
    Return informational capabilities.

    These do not grant access independently.
    Protected routes must use DoctorAdminDependency.
    """

    return DOCTOR_CAPABILITIES
