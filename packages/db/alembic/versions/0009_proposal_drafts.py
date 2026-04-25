"""proposal_drafts

Revision ID: 0009_proposal_drafts
Revises: 0008_library_tables
Create Date: 2026-04-25

Phase 3 Week 9. The Sources Sought drafter writes here. One row per
generated draft; parent_draft_id captures regeneration ancestry.

draft_type leaves room for rfp_response, compliance_matrix, and
white_paper drafts in later sprints.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0009_proposal_drafts"
down_revision: str | Sequence[str] | None = "0008_library_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_drafts",
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
            "parent_draft_id",
            UUID(as_uuid=True),
            sa.ForeignKey("proposal_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_founder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("draft_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("prompt_context_hash", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("citations", JSONB(), nullable=True),
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
        sa.CheckConstraint(
            "draft_type in ('sources_sought','rfp_response','compliance_matrix','white_paper')",
            name="ck_drafts_type",
        ),
        sa.CheckConstraint(
            "status in ('draft','reviewed','submitted','archived')",
            name="ck_drafts_status",
        ),
    )
    op.create_index(
        "ix_drafts_tenant_opp", "proposal_drafts", ["tenant_id", "opportunity_id"]
    )
    op.create_index(
        "ix_drafts_tenant_created", "proposal_drafts", ["tenant_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_drafts_tenant_created", table_name="proposal_drafts")
    op.drop_index("ix_drafts_tenant_opp", table_name="proposal_drafts")
    op.drop_table("proposal_drafts")
