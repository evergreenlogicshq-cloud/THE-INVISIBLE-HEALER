"""Phase 11 catalog tables.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def common_columns():
    return [
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
    ]


def upgrade():
    fields = {
        "products": [
            sa.Column("manufacturer", sa.String(200)),
            sa.Column("brand", sa.String(150)),
            sa.Column("dosage_form", sa.String(100)),
            sa.Column("product_category", sa.String(100)),
            sa.Column("country_of_origin", sa.String(100)),
            sa.Column("regulatory_number", sa.String(100)),
        ],
        "remedies": [
            sa.Column("remedy_type", sa.String(100)),
            sa.Column("preparation", sa.Text()),
            sa.Column("administration_route", sa.String(100)),
            sa.Column("limitations", sa.Text()),
        ],
        "ingredients": [
            sa.Column("scientific_name", sa.String(250)),
            sa.Column("ingredient_type", sa.String(100)),
            sa.Column("source_part", sa.String(100)),
            sa.Column("reference_amount", sa.Numeric(18, 6)),
            sa.Column("reference_unit", sa.String(30)),
            sa.Column("reference_basis", sa.String(200)),
            sa.CheckConstraint(
                "reference_amount IS NULL OR reference_amount > 0",
                name=op.f("ck_ingredients_reference_amount_positive"),
            ),
            sa.CheckConstraint(
                "(reference_amount IS NULL AND reference_unit IS NULL AND reference_basis IS NULL) OR (reference_amount IS NOT NULL AND reference_unit IS NOT NULL AND reference_basis IS NOT NULL)",
                name=op.f("ck_ingredients_reference_amount_complete"),
            ),
        ],
    }
    for table, columns in fields.items():
        op.create_table(
            table,
            *common_columns(),
            *columns,
            sa.PrimaryKeyConstraint("concept_id", name=op.f(f"pk_{table}")),
            sa.ForeignKeyConstraint(
                ["concept_id"],
                ["medical_concepts.id"],
                ondelete="RESTRICT",
                name=op.f(f"fk_{table}_concept_id_medical_concepts"),
            ),
            sa.CheckConstraint(
                "status IN ('draft', 'in_review', 'approved', 'retired')",
                name=op.f(f"ck_{table}_catalog_status"),
            ),
            sa.CheckConstraint(
                "version >= 1", name=op.f(f"ck_{table}_catalog_version")
            ),
        )
        op.create_index(f"ix_{table}_status", table, ["status"])


def downgrade():
    for table in ("ingredients", "remedies", "products"):
        op.drop_index(f"ix_{table}_status", table_name=table)
        op.drop_table(table)
