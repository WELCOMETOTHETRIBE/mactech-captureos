"""SBIR submission package tracking.

Revision ID: 0030_sbir_submissions
Revises: 0029_cyber_scope_downstream

Adds `sbir_submissions` for the new "SBIR Searcher & Submitter" page.
Tenant-scoped; unique on (tenant_id, topic_number) so re-submitting to
the same topic halts in Phase 0 per the engine prompt's duplicate-check
requirement.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_sbir_submissions"
down_revision: str | Sequence[str] | None = "0029_cyber_scope_downstream"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sbir_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_by_founder_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("topic_number", sa.String(64), nullable=False),
        sa.Column("topic_title", sa.String(512), nullable=True),
        sa.Column("proposal_title", sa.String(512), nullable=True),
        sa.Column("component", sa.String(32), nullable=False),
        sa.Column("depth", sa.String(16), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("output_dir", sa.String(512), nullable=False),
        sa.Column(
            "verify_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "file_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by_founder_id"], ["founders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "topic_number", name="uq_sbir_submissions_tenant_topic"
        ),
    )
    op.create_index(
        "ix_sbir_submissions_tenant_created",
        "sbir_submissions",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_sbir_submissions_tenant_created", table_name="sbir_submissions")
    op.drop_table("sbir_submissions")
