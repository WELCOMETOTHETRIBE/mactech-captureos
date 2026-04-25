"""opportunity_questions + opportunity_briefs

Revision ID: 0011_opp_qa_briefs
Revises: 0010_term_explanations
Create Date: 2026-04-25

Phase 3 Week 11. Two tables in one migration:

  opportunity_questions — Q&A history for the "Ask Claude about this opp"
  panel. Many rows per (tenant, opp).

  opportunity_briefs    — structured plain-English brief that replaces
  the raw SAM <pre> on the detail page. One row per (tenant, opp);
  regeneration overwrites in place via unique constraint.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0011_opp_qa_briefs"
down_revision: str | Sequence[str] | None = "0010_term_explanations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_questions",
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
            "asked_by_founder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("starter_kind", sa.String(32), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_opp_questions_tenant_opp_created",
        "opportunity_questions",
        ["tenant_id", "opportunity_id", "created_at"],
    )

    op.create_table(
        "opportunity_briefs",
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
        sa.Column("scope_one_sentence", sa.Text(), nullable=False),
        sa.Column("must_have_requirements", JSONB(), nullable=False),
        sa.Column("nice_to_have", JSONB(), nullable=False),
        sa.Column("red_flags_for_small_biz", JSONB(), nullable=False),
        sa.Column("suggested_team_roles", JSONB(), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("description_chars", sa.Integer(), nullable=True),
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
            "tenant_id", "opportunity_id", name="uq_opp_briefs_tenant_opp"
        ),
    )


def downgrade() -> None:
    op.drop_table("opportunity_briefs")
    op.drop_index(
        "ix_opp_questions_tenant_opp_created", table_name="opportunity_questions"
    )
    op.drop_table("opportunity_questions")
