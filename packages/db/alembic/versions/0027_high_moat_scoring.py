"""high_moat scoring + attachment_text + interested_vendors columns.

Revision ID: 0027_high_moat_scoring
Revises: 0026_tenant_sam_verification
Create Date: 2026-05-25

Adds the parallel high-moat (UFGS 25 / FRCS cyber) scoring track:

* ``opportunity_scores.high_moat_score`` (0..100, null if not yet computed)
* ``opportunity_scores.high_moat_breakdown`` — JSONB per-component points
* ``opportunity_scores.high_moat_flags`` — JSONB structured detector findings
  (clause_hits, clearance_hits, role_hits, top_clearance,
  is_high_probability_easy_win, why_it_matters_seed)
* ``opportunities_raw.attachment_text`` — concatenated PDF text from
  attachment_fetcher (gated by title heuristic / base score)
* ``opportunities_raw.attachments_fetched_at``
* ``opportunities_raw.interested_vendors_count`` —
  SAM.gov Interested Vendors List total
* ``opportunities_raw.interested_vendors_cyber_count`` — subset whose
  NAICS profile intersects {541512, 541513, 541519, 518210}
* ``opportunities_raw.interested_vendors_fetched_at``

Plus a partial covering index for the morning digest's top-N query:
``(tenant_id, high_moat_score DESC) WHERE high_moat_score IS NOT NULL``.

All columns are null-tolerant — old rows score on next pass.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_high_moat_scoring"
down_revision: str | Sequence[str] | None = "0026_tenant_sam_verification"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # opportunity_scores: parallel high-moat track
    op.add_column(
        "opportunity_scores",
        sa.Column("high_moat_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("high_moat_breakdown", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("high_moat_flags", postgresql.JSONB(), nullable=True),
    )

    # opportunities_raw: attachment text + interested vendors
    op.add_column(
        "opportunities_raw",
        sa.Column("attachment_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "opportunities_raw",
        sa.Column(
            "attachments_fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "opportunities_raw",
        sa.Column("interested_vendors_count", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "opportunities_raw",
        sa.Column(
            "interested_vendors_cyber_count",
            sa.BigInteger(),
            nullable=True,
        ),
    )
    op.add_column(
        "opportunities_raw",
        sa.Column(
            "interested_vendors_fetched_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    # Partial covering index for "top N by high_moat_score per tenant".
    # Postgres-only — we can rely on it; the db package targets Postgres 16.
    op.create_index(
        "idx_opp_scores_high_moat",
        "opportunity_scores",
        ["tenant_id", sa.text("high_moat_score DESC")],
        postgresql_where=sa.text("high_moat_score IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_opp_scores_high_moat", table_name="opportunity_scores")

    op.drop_column("opportunities_raw", "interested_vendors_fetched_at")
    op.drop_column("opportunities_raw", "interested_vendors_cyber_count")
    op.drop_column("opportunities_raw", "interested_vendors_count")
    op.drop_column("opportunities_raw", "attachments_fetched_at")
    op.drop_column("opportunities_raw", "attachment_text")

    op.drop_column("opportunity_scores", "high_moat_flags")
    op.drop_column("opportunity_scores", "high_moat_breakdown")
    op.drop_column("opportunity_scores", "high_moat_score")
