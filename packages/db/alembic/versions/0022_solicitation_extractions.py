"""solicitation_extractions + compliance_matrix_items + requirement_matrix_items.

Revision ID: 0022_solicitation_extractions
Revises: 0021_tenant_sprs
Create Date: 2026-04-29

Section C of CaptureOS_Requirements.md — solicitation decoder.

V1 takes the opportunity description text we already have and uses Claude
to extract two structured matrices:

  compliance_matrix_items   — every "shall" from Section L (instructions
                              to offerors). Used by ProposalOS as the
                              spine of the proposal — every section
                              must address an item.

  requirement_matrix_items  — every technical / operational / security
                              obligation from the SOW / PWS / CDRLs.

Each generation run is tracked in solicitation_extractions: one row per
(tenant, opportunity), upserted on regeneration. Items belong to a
specific extraction run via extraction_id; previous items are deleted
on regeneration so the matrices always reflect the latest extraction.

V2 (when full file ingest lands) will feed solicitation attachments,
amendments, and exhibits into the same extractor — same schema, fuller
inputs.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0022_solicitation_extractions"
down_revision: str | Sequence[str] | None = "0021_tenant_sprs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "solicitation_extractions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("source_text_hash", sa.String(64), nullable=True),
        sa.Column("description_chars", sa.Integer(), nullable=True),
        sa.Column("compliance_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requirements_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "opportunity_id", name="uq_solicitation_extractions_tenant_opp"
        ),
    )

    op.create_table(
        "compliance_matrix_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "extraction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("section_l_citation", sa.String(255), nullable=True),
        sa.Column("pass_fail", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_compliance_items_tenant_opp_sort",
        "compliance_matrix_items",
        ["tenant_id", "opportunity_id", "sort_order"],
    )

    op.create_table(
        "requirement_matrix_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "extraction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_id", sa.String(32), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_citation", sa.String(255), nullable=True),
        sa.Column("category", sa.String(32), nullable=False, server_default="other"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_requirement_items_tenant_opp_sort",
        "requirement_matrix_items",
        ["tenant_id", "opportunity_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_requirement_items_tenant_opp_sort", table_name="requirement_matrix_items"
    )
    op.drop_table("requirement_matrix_items")
    op.drop_index(
        "ix_compliance_items_tenant_opp_sort", table_name="compliance_matrix_items"
    )
    op.drop_table("compliance_matrix_items")
    op.drop_table("solicitation_extractions")
