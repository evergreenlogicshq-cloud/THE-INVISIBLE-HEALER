"""Central SQLAlchemy model registry.

All ORM models must be imported here for
Base.metadata and Alembic discovery.
"""

from app.models.admin import (
    AdminLoginAttempt,
    AdminSession,
    AdminUser,
    AuditEvent,
    ConceptAlias,
    HealthIssue,
    MedicalConcept,
    Symptom,
)

__all__ = [
    "AdminLoginAttempt",
    "AdminSession",
    "AdminUser",
    "AuditEvent",
    "ConceptAlias",
    "HealthIssue",
    "MedicalConcept",
    "Symptom",
]
