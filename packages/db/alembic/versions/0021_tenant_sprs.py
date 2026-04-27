"""tenants: SPRS score columns (consumed from Codex).

Revision ID: 0021_tenant_sprs
Revises: 0020_incumbent_signals
Create Date: 2026-04-27

Sprint 23. CMMC Readiness Engine lives in a sibling product (Codex,
codex.mactechsolutionsllc.com). CaptureOS just consumes the published
SPRS score for the tenant — it's a meaningful eligibility signal that
shows up on dashboard + against opportunities with CMMC requirements.

  sprs_score              0..110 (or 0..200 for some scales) — int
  sprs_max                scale ceiling, default 110
  sprs_assessment_date    when last assessed
  sprs_source_url         deep-link to Codex assessment view
  sprs_synced_at          when CaptureOS last refreshed from Codex
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_tenant_sprs"
down_revision: str | Sequence[str] | None = "0020_incumbent_signals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("sprs_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("sprs_max", sa.Integer(), nullable=False, server_default="110"),
    )
    op.add_column(
        "tenants",
        sa.Column("sprs_assessment_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("sprs_source_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "sprs_synced_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "sprs_synced_at")
    op.drop_column("tenants", "sprs_source_url")
    op.drop_column("tenants", "sprs_assessment_date")
    op.drop_column("tenants", "sprs_max")
    op.drop_column("tenants", "sprs_score")
