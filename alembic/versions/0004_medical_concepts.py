"""Phase 09 - Medical concept taxonomy.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_concepts",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("namespace", sa.String(60), nullable=False),
        sa.Column("canonical_name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("ontology_code", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
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
            "retired_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_medical_concepts"),
        sa.UniqueConstraint(
            "namespace",
            "normalized_name",
            name="uq_medical_concepts_namespace_name",
        ),
        sa.CheckConstraint(
            "kind IN ("
            "'health_issue', 'symptom', 'medication', "
            "'product', 'remedy', 'ingredient')",
            name="ck_medical_concepts_concept_kind",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'retired')",
            name="ck_medical_concepts_concept_status",
        ),
    )

    op.create_index(
        "ix_medical_concepts_kind_status",
        "medical_concepts",
        ["kind", "status"],
    )

    op.create_table(
        "concept_aliases",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "concept_id",
            sa.Uuid(as_uuid=True),
            nullable=False,
        ),
        sa.Column("namespace", sa.String(60), nullable=False),
        sa.Column("alias", sa.String(200), nullable=False),
        sa.Column(
            "normalized_alias",
            sa.String(200),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_concept_aliases"),
        sa.ForeignKeyConstraint(
            ["concept_id"],
            ["medical_concepts.id"],
            name="fk_concept_aliases_concept_id_medical_concepts",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "namespace",
            "normalized_alias",
            name="uq_concept_aliases_namespace_name",
        ),
    )

    op.create_index(
        "ix_concept_aliases_concept_id",
        "concept_aliases",
        ["concept_id"],
    )

    op.create_index(
        "ix_concept_aliases_lookup",
        "concept_aliases",
        ["normalized_alias"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_aliases_lookup",
        table_name="concept_aliases",
    )
    op.drop_index(
        "ix_concept_aliases_concept_id",
        table_name="concept_aliases",
    )
    op.drop_table("concept_aliases")

    op.drop_index(
        "ix_medical_concepts_kind_status",
        table_name="medical_concepts",
    )
    op.drop_table("medical_concepts")
