"""incumbent_signals — SEC EDGAR distress monitoring.

Revision ID: 0020_incumbent_signals
Revises: 0019_forecasts_raw
Create Date: 2026-04-27

Sprint 22. For the top-N federal contractors (by USASpending
obligated $$), we monitor recent SEC EDGAR filings (8-K / 10-Q / 10-K)
and surface distress signals (layoffs, investigations, going-concern
language, contract disputes) on recompete cards.

Identity is name-keyed because forecasts only carry incumbent names;
we backfill cik / sec_ticker when matched. recipient_uei links to
awards_history when we can find the same name there.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0020_incumbent_signals"
down_revision: str | Sequence[str] | None = "0019_forecasts_raw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incumbent_signals",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("recipient_uei", sa.String(16), nullable=True),
        sa.Column("cik", sa.String(16), nullable=True),
        sa.Column("sec_ticker", sa.String(16), nullable=True),
        sa.Column("sec_title", sa.String(255), nullable=True),
        sa.Column("filings_last_90d_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filings_last_365d_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("most_recent_filing_form", sa.String(16), nullable=True),
        sa.Column("most_recent_filing_date", sa.Date(), nullable=True),
        sa.Column("most_recent_8k_items", JSONB(), nullable=True),
        sa.Column(
            "distress_score",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="0..100 — heuristic flag derived from filings cadence + 8-K item codes",
        ),
        sa.Column("distress_summary", sa.Text(), nullable=True),
        sa.Column("filings", JSONB(), nullable=True, comment="last 10 filings for surface display"),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_refreshed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("normalized_name", name="uq_incumbent_signals_name"),
    )
    op.create_index(
        "ix_incumbent_signals_distress",
        "incumbent_signals",
        ["distress_score"],
    )
    op.create_index(
        "ix_incumbent_signals_uei",
        "incumbent_signals",
        ["recipient_uei"],
    )


def downgrade() -> None:
    op.drop_index("ix_incumbent_signals_uei", table_name="incumbent_signals")
    op.drop_index("ix_incumbent_signals_distress", table_name="incumbent_signals")
    op.drop_table("incumbent_signals")
