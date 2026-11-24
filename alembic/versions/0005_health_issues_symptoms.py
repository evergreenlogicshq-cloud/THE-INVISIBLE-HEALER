"""Phase 10 - Health issues and symptoms.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def common_columns() -> list[sa.Column]:
    """Return independent columns for each subtype table."""

    return [
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reviewed_by",
            sa.Uuid(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "review_notes",
            sa.Text(),
            nullable=True,
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
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "retired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    ]


def upgrade() -> None:
    # Health issue subtype table.
    op.create_table(
        "health_issues",
        *common_columns(),
        sa.Column(
            "body_system",
            sa.String(100),
            nullable=True,
        ),
        sa.Column(
            "clinical_category",
            sa.String(100),
            nullable=True,
        ),
        sa.Column(
            "typical_course",
            sa.String(20),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "concept_id",
            name=op.f("pk_health_issues"),
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["medical_concepts.id"],
            name=op.f("fk_health_issues_concept_id_medical_concepts"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'retired')",
            name=op.f("ck_health_issues_health_issue_status"),
        ),
        sa.CheckConstraint(
            "typical_course IN "
            "('acute', 'chronic', 'recurrent', 'variable', 'unknown')",
            name=op.f("ck_health_issues_health_issue_course"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_health_issues_health_issue_version"),
        ),
    )

    op.create_index(
        "ix_health_issues_status",
        "health_issues",
        ["status"],
    )

    # Symptom subtype table.
    op.create_table(
        "symptoms",
        *common_columns(),
        sa.Column(
            "body_location",
            sa.String(100),
            nullable=True,
        ),
        sa.Column(
            "symptom_category",
            sa.String(100),
            nullable=True,
        ),
        sa.Column(
            "observation_type",
            sa.String(20),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "concept_id",
            name=op.f("pk_symptoms"),
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["medical_concepts.id"],
            name=op.f("fk_symptoms_concept_id_medical_concepts"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'in_review', 'approved', 'retired')",
            name=op.f("ck_symptoms_symptom_status"),
        ),
        sa.CheckConstraint(
            "observation_type IN ('subjective', 'objective', 'both', 'unknown')",
            name=op.f("ck_symptoms_symptom_observation_type"),
        ),
        sa.CheckConstraint(
            "version >= 1",
            name=op.f("ck_symptoms_symptom_version"),
        ),
    )

    op.create_index(
        "ix_symptoms_status",
        "symptoms",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_symptoms_status",
        table_name="symptoms",
    )
    op.drop_table("symptoms")
    op.drop_index(
        "ix_health_issues_status",
        table_name="health_issues",
    )
    op.drop_table("health_issues")
