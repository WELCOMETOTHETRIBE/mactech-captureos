"""forecasts_raw — agency procurement forecasts (pre-SAM intent).

Revision ID: 0019_forecasts_raw
Revises: 0018_apify_and_events
Create Date: 2026-04-26

Sprint 20 / strategy doc §3.1 ("Agency Forecast Sweep"). Federal
agencies publish procurement forecasts (DoD OSBP, VA, DHS APFS, GSA
Forecast tool, etc.) 30-180 days before the corresponding solicitation
appears in SAM.gov. Capturing these gives MacTech a multi-month head
start on incumbent recompetes.

Schema mirrors opportunities_raw conceptually but distinct:
  - source_url + title is the dedup identity (forecasts rarely have
    canonical IDs across agencies)
  - estimated_value can be a range string ("$2M-$5M") when the agency
    publishes brackets rather than discrete numbers
  - expected_solicitation_date / expected_award_date capture the
    "coming to SAM" timeline that's the whole point
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0019_forecasts_raw"
down_revision: str | Sequence[str] | None = "0018_apify_and_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecasts_raw",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_host", sa.String(128), nullable=True),
        sa.Column(
            "source_run_id",
            sa.String(64),
            nullable=True,
            comment="Apify run id that produced this forecast",
        ),
        sa.Column("agency", sa.String(255), nullable=True),
        sa.Column("contracting_office", sa.String(512), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("naics_code", sa.String(8), nullable=True),
        sa.Column("naics_codes", JSONB(), nullable=True),
        sa.Column("set_aside", sa.String(64), nullable=True),
        sa.Column("contract_type", sa.String(64), nullable=True),
        sa.Column("estimated_value_low", sa.Numeric(15, 2), nullable=True),
        sa.Column("estimated_value_high", sa.Numeric(15, 2), nullable=True),
        sa.Column("estimated_value_text", sa.String(128), nullable=True),
        sa.Column(
            "expected_solicitation_date",
            sa.Date(),
            nullable=True,
            comment="When the agency expects to post the RFP to SAM",
        ),
        sa.Column("expected_award_date", sa.Date(), nullable=True),
        sa.Column("period_of_performance_start", sa.Date(), nullable=True),
        sa.Column("period_of_performance_end", sa.Date(), nullable=True),
        sa.Column("incumbent_name", sa.String(255), nullable=True),
        sa.Column("incumbent_contract_number", sa.String(64), nullable=True),
        sa.Column("poc_name", sa.String(128), nullable=True),
        sa.Column("poc_email", sa.String(255), nullable=True),
        sa.Column(
            "forecast_id",
            sa.String(128),
            nullable=True,
            comment="Agency-internal identifier when present",
        ),
        sa.Column(
            "raw",
            JSONB(),
            nullable=True,
            comment="Full extracted record + extraction metadata",
        ),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "closed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When the forecast no longer appears in the agency feed",
        ),
        sa.UniqueConstraint(
            "source_url", "title", name="uq_forecasts_raw_url_title"
        ),
    )
    op.create_index(
        "ix_forecasts_raw_solicitation_date",
        "forecasts_raw",
        ["expected_solicitation_date"],
    )
    op.create_index(
        "ix_forecasts_raw_naics_code", "forecasts_raw", ["naics_code"]
    )
    op.create_index(
        "ix_forecasts_raw_agency", "forecasts_raw", ["agency"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_forecasts_raw_agency", table_name="forecasts_raw"
    )
    op.drop_index(
        "ix_forecasts_raw_naics_code", table_name="forecasts_raw"
    )
    op.drop_index(
        "ix_forecasts_raw_solicitation_date", table_name="forecasts_raw"
    )
    op.drop_table("forecasts_raw")
