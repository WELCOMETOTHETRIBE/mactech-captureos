"""Per-founder bid-invite seen watermark + arrival-order index.

Revision ID: 0037_bid_invite_seen_watermark
Revises: 0036_drop_sbirdashboard_topics

Two problems this fixes.

1. "New" meant "never triaged" (status='new'), which is a backlog, not a
   signal — 58 of 63 rows qualified, so genuinely new mail was
   indistinguishable. `founders.bid_invites_seen_at` is a per-founder
   watermark: an invite is *unseen* when it arrived after the founder
   last acknowledged the inbox. Status stays the durable triage state;
   unseen is the transient "since you last looked" signal.

2. Ordering ran on `received_at` (ingest time). The mbox backfill
   replayed historical mail through the webhook, so every imported row
   carries the import timestamp and the true chronology sits unused in
   `sent_at`. Arrival order is `coalesce(sent_at, received_at)` — the
   expression index below backs that sort, which `received_at` never
   had one for either.

The watermark seeds to now() - 24h rather than NULL: NULL would mark the
entire backfilled corpus unseen on first load, which is the exact noise
this is meant to kill. A 24h seed makes the last day of mail visible so
the signal starts out true, and every arrival after this migration is
tracked exactly.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_bid_invite_seen_watermark"
down_revision: str | Sequence[str] | None = "0036_drop_sbirdashboard_topics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "founders",
        sa.Column(
            "bid_invites_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    # server_default catches founders added later; existing rows get the
    # 24h seed so today's mail reads as unseen on first load.
    op.execute("update founders set bid_invites_seen_at = now() - interval '24 hours'")
    # Backs `order by coalesce(sent_at, received_at) desc` in
    # GET /bid-invites. Must match the query expression exactly or the
    # planner won't use it.
    op.execute(
        """
        create index ix_bid_invites_tenant_arrived
        on bid_invites (tenant_id, coalesce(sent_at, received_at) desc)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_bid_invites_tenant_arrived", table_name="bid_invites")
    op.drop_column("founders", "bid_invites_seen_at")
