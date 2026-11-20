"""Phase 08 - Append-only audit events.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "actor_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=80),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "resource_version",
            sa.String(length=80),
            nullable=True,
        ),
        sa.Column(
            "decision",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "trace_id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name="pk_audit_events",
        ),
        sa.CheckConstraint(
            "actor_type IN ('doctor_admin', 'system')",
            name="ck_audit_events_actor_type",
        ),
        sa.CheckConstraint(
            "decision IN ('allowed', 'denied', 'failed')",
            name="ck_audit_events_decision",
        ),
    )

    op.create_index(
        "ix_audit_events_occurred_at",
        "audit_events",
        ["occurred_at"],
    )
    op.create_index(
        "ix_audit_events_actor_time",
        "audit_events",
        ["actor_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_resource",
        "audit_events",
        ["resource_type", "resource_id"],
    )
    op.create_index(
        "ix_audit_events_trace_id",
        "audit_events",
        ["trace_id"],
    )

    # SQLite is used only for isolated tests.
    # The production system uses PostgreSQL.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION prevent_audit_event_mutation()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION
                    'Audit events cannot be modified or deleted';
            END;
            $$;
            """
        )

        op.execute(
            """
            CREATE TRIGGER audit_events_append_only
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )

        op.execute(
            """
            CREATE TRIGGER audit_events_no_truncate
            BEFORE TRUNCATE ON audit_events
            FOR EACH STATEMENT
            EXECUTE FUNCTION prevent_audit_event_mutation();
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_events_no_truncate ON audit_events")
        op.execute("DROP TRIGGER audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION prevent_audit_event_mutation()")

    op.drop_index(
        "ix_audit_events_trace_id",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_events_resource",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_events_actor_time",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_events_occurred_at",
        table_name="audit_events",
    )

    op.drop_table("audit_events")
