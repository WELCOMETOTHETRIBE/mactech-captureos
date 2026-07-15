"""Bid invites forwarded in by email (Postmark inbound webhook).

Revision ID: 0033_bid_invites
Revises: 0032_sbir_topic_dsip_enrichment

Tenant-scoped table populated by POST /webhooks/postmark/inbound.
Unique postmark_message_id makes webhook retries idempotent.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_bid_invites"
down_revision: str | Sequence[str] | None = "0032_sbir_topic_dsip_enrichment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bid_invites",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("postmark_message_id", sa.String(64), nullable=False),
        sa.Column("from_email", sa.String(320), nullable=True),
        sa.Column("from_name", sa.String(320), nullable=True),
        sa.Column("subject", sa.String(1024), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column(
            "attachments",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default=sa.text("'new'"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('new','reviewed','archived')",
            name="ck_bid_invites_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("postmark_message_id"),
    )
    op.create_index(
        "ix_bid_invites_tenant_status", "bid_invites", ["tenant_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_bid_invites_tenant_status", table_name="bid_invites")
    op.drop_table("bid_invites")
