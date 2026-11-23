"""Central SQLAlchemy model registry.

Every ORM model must be imported here
for Base.metadata and Alembic discovery.
"""

from app.models.admin.admin_user import AdminLoginAttempt, AdminSession, AdminUser
from app.models.admin.audit import AuditEvent
from app.models.admin.concept import ConceptAlias, MedicalConcept

__all__ = [
    "AdminLoginAttempt",
    "AdminSession",
    "AdminUser",
    "AuditEvent",
    "ConceptAlias",
    "MedicalConcept",
]
