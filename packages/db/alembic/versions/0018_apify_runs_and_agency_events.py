"""apify_runs audit + agency_events.

Revision ID: 0018_apify_and_events
Revises: 0017_web_mention_cache
Create Date: 2026-04-26

Sprint 19. Two tables:

  apify_runs       Append-only audit of every Apify webhook we accept,
                   keyed by Apify run id. Lets us trace ingest back to
                   the source actor + dataset and dedupe on resends.

  agency_events    Industry days, pre-solicitation conferences, and
                   "meet the buyer" events scraped by the Apify
                   `apify/website-content-crawler` daily beat. Tenant-
                   shared (events are public-data signal, not per-tenant
                   intel) and indexed on starts_at + naics for the
                   dashboard "Where to be" tile.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0018_apify_and_events"
down_revision: str | Sequence[str] | None = "0017_web_mention_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "apify_runs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("apify_run_id", sa.String(64), nullable=False),
        sa.Column("apify_actor_id", sa.String(128), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("apify_status", sa.String(32), nullable=True),
        sa.Column("dataset_id", sa.String(64), nullable=True),
        sa.Column("items_count", sa.Integer(), nullable=True),
        sa.Column("ingest_error", sa.Text(), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "apify_run_id", "event_type", name="uq_apify_runs_run_event"
        ),
    )
    op.create_index(
        "ix_apify_runs_capability_received",
        "apify_runs",
        ["capability", "received_at"],
    )

    op.create_table(
        "agency_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_host", sa.String(128), nullable=True),
        sa.Column("agency", sa.String(255), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(48), nullable=True),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("registration_url", sa.Text(), nullable=True),
        sa.Column("naics_codes", JSONB(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
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
        sa.Column("apify_run_id", sa.String(64), nullable=True),
        sa.Column(
            "raw",
            JSONB(),
            nullable=True,
            comment="Full extracted record + extraction metadata",
        ),
        sa.UniqueConstraint(
            "source_url", "title", name="uq_agency_events_url_title"
        ),
    )
    op.create_index(
        "ix_agency_events_starts_at", "agency_events", ["starts_at"]
    )
    op.create_index(
        "ix_agency_events_agency", "agency_events", ["agency"]
    )


def downgrade() -> None:
    op.drop_index("ix_agency_events_agency", table_name="agency_events")
    op.drop_index("ix_agency_events_starts_at", table_name="agency_events")
    op.drop_table("agency_events")
    op.drop_index(
        "ix_apify_runs_capability_received", table_name="apify_runs"
    )
    op.drop_table("apify_runs")
