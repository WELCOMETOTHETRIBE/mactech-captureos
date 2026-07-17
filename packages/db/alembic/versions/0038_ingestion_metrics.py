"""Per-run retrieval metrics on ingestion_state.

Revision ID: 0038_ingestion_metrics
Revises: 0037_bid_invite_seen_watermark

Slice 1 of the capture-engine overhaul broadens SAM retrieval into five query
families. Before precision (document parsing, signal detection) grows on top of
that wider candidate universe, we need to see what each family actually pulls.

``ingestion_state.metrics`` is a nullable JSONB blob written per state row
(one per saved-search family x NAICS/title job) holding the last run's
``{examined, matched, inserted, updated, pages, posted_from, posted_to}``. It is
purely observational — no behavior keys on it — so the families stay tunable
from the knowledge-pack YAML without code changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0038_ingestion_metrics"
down_revision: str | Sequence[str] | None = "0037_bid_invite_seen_watermark"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingestion_state",
        sa.Column("metrics", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_state", "metrics")
