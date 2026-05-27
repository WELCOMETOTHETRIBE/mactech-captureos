"""Clause risk logs, bid/no-bid reviews, proposal outlines from cyber scope.

Revision ID: 0029_cyber_scope_downstream
Revises: 0028_cyber_scope
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0029_cyber_scope_downstream"
down_revision: str | Sequence[str] | None = "0028_cyber_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clause_risk_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cyber_scope_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities_raw.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["cyber_scope_analysis_id"], ["cyber_scope_analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "cyber_scope_analysis_id",
            name="uq_clause_risk_logs_tenant_analysis",
        ),
    )
    op.create_index("ix_clause_risk_logs_tenant_opp", "clause_risk_logs", ["tenant_id", "opportunity_id"])

    op.create_table(
        "clause_risk_log_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("reference", sa.String(255), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("mitigation", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["log_id"], ["clause_risk_logs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clause_risk_log_entries_log", "clause_risk_log_entries", ["log_id"])

    op.create_table(
        "bid_no_bid_reviews",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cyber_scope_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pursuit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "recommended_decision",
            sa.String(16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("cyber_scope_summary", sa.Text(), nullable=False),
        sa.Column(
            "factors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("rationale_draft", sa.Text(), nullable=False),
        sa.Column("pursuit_model", sa.String(32), nullable=True),
        sa.Column("likelihood", sa.String(16), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities_raw.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["cyber_scope_analysis_id"], ["cyber_scope_analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["pursuit_id"], ["pursuits.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "cyber_scope_analysis_id",
            name="uq_bid_no_bid_reviews_tenant_analysis",
        ),
    )

    op.create_table(
        "proposal_outlines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cyber_scope_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column(
            "sections_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities_raw.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["cyber_scope_analysis_id"], ["cyber_scope_analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "cyber_scope_analysis_id",
            name="uq_proposal_outlines_tenant_analysis",
        ),
    )


def downgrade() -> None:
    op.drop_table("proposal_outlines")
    op.drop_table("bid_no_bid_reviews")
    op.drop_table("clause_risk_log_entries")
    op.drop_table("clause_risk_logs")
