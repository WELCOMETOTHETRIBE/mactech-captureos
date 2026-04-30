"""opportunity_amendments + audit_events + pursuits.bid_decision columns.

Revision ID: 0024_amendments_audit_bid_decision
Revises: 0023_pursuit_links_evaluation
Create Date: 2026-04-29

Tier-1 catch-up sprint per the requirements audit. Closes:

* Section G (amendment tracking) — adds ``opportunity_amendments`` so SAM
  ingest can record whenever an existing opportunity's content hash
  changes. Tenant-agnostic (amendments are facts about the opportunity);
  notification fan-out happens via the join from pursuits.

* D7 (audit trail) — adds ``audit_events`` so every meaningful change to
  a pursuit (stage flow, bid decision, owner change, asset selection)
  and every amendment ingestion is logged with who / when / why beyond
  row-level timestamps.

* D3 (structured bid memo) — adds ``pursuits.bid_decision`` /
  ``bid_decided_at`` / ``bid_decided_by_user_id`` / ``bid_rationale`` so
  the Capture Package's BidDecisionSection can carry real structured
  data rather than inferring from stage + free-form notes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0024_amendments_audit_bid_decision"
down_revision: str | Sequence[str] | None = "0023_pursuit_links_evaluation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── opportunity_amendments ─────────────────────────────────────
    op.create_table(
        "opportunity_amendments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("new_hash", sa.String(64), nullable=False),
        sa.Column(
            "previous_response_deadline",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "new_response_deadline",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("previous_title", sa.Text(), nullable=True),
        sa.Column("new_title", sa.Text(), nullable=True),
        sa.Column("diff_summary", JSONB(), nullable=False),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_opportunity_amendments_opp_detected",
        "opportunity_amendments",
        ["opportunity_id", "detected_at"],
    )

    # ── audit_events ───────────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_founder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_label", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_audit_events_tenant_created",
        "audit_events",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_audit_events_entity",
        "audit_events",
        ["entity_type", "entity_id", sa.text("created_at DESC")],
    )

    # ── pursuits: structured bid decision ──────────────────────────
    op.add_column(
        "pursuits",
        sa.Column(
            "bid_decision",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.create_check_constraint(
        "ck_pursuits_bid_decision",
        "pursuits",
        "bid_decision in ('pending', 'bid', 'no_bid')",
    )
    op.add_column(
        "pursuits",
        sa.Column(
            "bid_decided_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "pursuits",
        sa.Column(
            "bid_decided_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "pursuits",
        sa.Column("bid_rationale", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pursuits", "bid_rationale")
    op.drop_column("pursuits", "bid_decided_by_user_id")
    op.drop_column("pursuits", "bid_decided_at")
    op.drop_constraint("ck_pursuits_bid_decision", "pursuits", type_="check")
    op.drop_column("pursuits", "bid_decision")

    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(
        "ix_opportunity_amendments_opp_detected",
        table_name="opportunity_amendments",
    )
    op.drop_table("opportunity_amendments")
