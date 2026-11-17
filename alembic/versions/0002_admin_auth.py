"""Phase 06 - Admin identities and secure sessions.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=254),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sa.String(length=512),
            nullable=False,
        ),
        sa.Column(
            "full_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_users"),
    )

    op.create_index(
        "ix_admin_users_email",
        "admin_users",
        ["email"],
        unique=True,
    )

    op.create_table(
        "admin_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "csrf_secret",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["admin_users.id"],
            name="fk_admin_sessions_user_id_admin_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_sessions"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_admin_sessions_token_hash",
        ),
    )
    op.create_index(
        "ix_admin_sessions_user_id",
        "admin_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_admin_sessions_expires_at",
        "admin_sessions",
        ["expires_at"],
    )
    op.create_table(
        "admin_login_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "client_key",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_admin_login_attempts",
        ),
    )

    op.create_index(
        "ix_admin_login_attempts_key_time",
        "admin_login_attempts",
        ["client_key", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_login_attempts_key_time",
        table_name="admin_login_attempts",
    )
    op.drop_table("admin_login_attempts")
    op.drop_index(
        "ix_admin_sessions_expires_at",
        table_name="admin_sessions",
    )
    op.drop_index(
        "ix_admin_sessions_user_id",
        table_name="admin_sessions",
    )
    op.drop_table("admin_sessions")
    op.drop_index(
        "ix_admin_users_email",
        table_name="admin_users",
    )
    op.drop_table("admin_users")
