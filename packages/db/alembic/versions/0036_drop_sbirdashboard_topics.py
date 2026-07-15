"""Purge sbirdashboard-sourced SBIR topics.

Revision ID: 0036_drop_sbirdashboard_topics
Revises: 0035_bid_invite_pipeline_link

The sbirdashboard.com ingest path was removed in favor of pulling SBIR/STTR
topics directly from DSIP (dodsbirsttr.mil) via its public API. Any rows
left with source='sbirdashboard' would shadow the richer source='dsip' rows
for the same topic_number (they share topic_number but differ on the source
uniqueness key), producing duplicate topic cards. Delete them.

This is data-only — the `sbir_topics` table and its columns are unchanged,
so downgrade is a no-op (the sbirdashboard rows are re-created only if the
old ingest is reinstated, which this migration is part of undoing).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0036_drop_sbirdashboard_topics"
down_revision: str | Sequence[str] | None = "0035_bid_invite_pipeline_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM sbir_topics WHERE source = 'sbirdashboard'")


def downgrade() -> None:
    # Data-only forward migration; nothing to restore.
    pass
