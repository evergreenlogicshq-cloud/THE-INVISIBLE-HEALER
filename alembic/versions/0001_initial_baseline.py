"""
The Invisible Healer
Phase 04 - Initial Migration Baseline

Revision ID: 0001
Revises: None

Purpose:
    Establish the initial Alembic revision
    without creating clinical application tables.

This revision is intentionally empty.

Alembic manages its own alembic_version table.

Future migrations:
    Phase 06 - Admin users and sessions
    Phase 07 - Roles and permissions
    Phase 08 - Audit events
    Phase 09 - Medical concepts
"""

from collections.abc import Sequence

# ============================================
# REVISION IDENTIFIERS
# ============================================

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ============================================
# UPGRADE
# ============================================


def upgrade() -> None:
    """
    Establish the initial migration baseline.
    No application tables are created here.
    The Alembic runtime maintains
    the alembic_version tracking table.
    """


# ============================================
# DOWNGRADE
# ============================================


def downgrade() -> None:
    """
    Reverse the initial baseline.
    No application table drops are required.
    """
