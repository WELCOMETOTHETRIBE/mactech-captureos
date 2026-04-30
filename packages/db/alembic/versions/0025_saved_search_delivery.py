"""saved_searches: last_delivered_at column for digest dedupe.

Revision ID: 0025_saved_search_delivery
Revises: 0024_amendments_audit_bid_decision
Create Date: 2026-04-29

Closes I1 — wires the existing alert_threshold/cadence/channels columns
on saved_searches through the morning digest worker so each saved
search delivers its hits at most once per cadence interval. Adds a
single ``last_delivered_at`` column the worker updates after every
successful send.

Backfill: leave NULL on first run so the first-ever digest delivery
for an existing saved search includes everything currently above
threshold (with the existing 5-item cap per search to keep the email
sane).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_saved_search_delivery"
down_revision: str | Sequence[str] | None = "0024_amendments_audit_bid_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saved_searches",
        sa.Column(
            "last_delivered_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("saved_searches", "last_delivered_at")
