"""agency_naics_intel cache + pg_trgm extension

Revision ID: 0012_agency_intel
Revises: 0011_opp_qa_briefs
Create Date: 2026-04-25

Phase 3 Week 12 (UX Sprint 5). Two changes:

  1. agency_naics_intel — cached USASpending rollups for the
     "Agency intel" card on the opp detail page.

  2. CREATE EXTENSION pg_trgm IF NOT EXISTS — needed by the Cmd-K
     hybrid search (similarity over titles). Idempotent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0012_agency_intel"
down_revision: str | Sequence[str] | None = "0011_opp_qa_briefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "agency_naics_intel",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("agency_name", sa.String(255), nullable=False),
        sa.Column("naics_code", sa.String(8), nullable=False),
        sa.Column(
            "lookback_days", sa.Integer(), nullable=False, server_default="365"
        ),
        sa.Column(
            "award_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("total_obligated", sa.Numeric(16, 2), nullable=True),
        sa.Column("avg_award_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("median_award_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("top_recipients", JSONB(), nullable=True),
        sa.Column("set_aside_breakdown", JSONB(), nullable=True),
        sa.Column(
            "lookup_failed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("failure_note", sa.String(255), nullable=True),
        sa.Column("sample_size", sa.Integer(), nullable=True),
        sa.Column(
            "refreshed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "agency_name",
            "naics_code",
            "lookback_days",
            name="uq_agency_intel_lookup",
        ),
    )
    op.create_index(
        "ix_agency_intel_refreshed",
        "agency_naics_intel",
        ["agency_name", "naics_code", "refreshed_at"],
    )

    # pg_trgm GIN indexes on title columns used by the Cmd-K search.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_opportunities_raw_title_trgm "
        "ON opportunities_raw USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proposal_drafts_title_trgm "
        "ON proposal_drafts USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_teaming_partners_name_trgm "
        "ON teaming_partners USING gin (name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_past_performance_title_trgm "
        "ON past_performance USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_past_performance_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_teaming_partners_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_proposal_drafts_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_opportunities_raw_title_trgm")
    op.drop_index("ix_agency_intel_refreshed", table_name="agency_naics_intel")
    op.drop_table("agency_naics_intel")
    # pg_trgm extension stays — other features may rely on it.
