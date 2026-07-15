"""Parsed BuildingConnected fields on bid_invites.

Revision ID: 0034_bid_invite_parsing
Revises: 0033_bid_invites

Populated at webhook ingest by mactech_intelligence.bid_invite_parser;
historical rows are backfilled via POST /bid-invites/reparse.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_bid_invite_parsing"
down_revision: str | Sequence[str] | None = "0033_bid_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    sa.Column("kind", sa.String(24), nullable=True),
    sa.Column("project_name", sa.String(512), nullable=True),
    sa.Column("bid_package", sa.String(512), nullable=True),
    sa.Column("gc_company", sa.String(320), nullable=True),
    sa.Column("lead_name", sa.String(320), nullable=True),
    sa.Column("lead_email", sa.String(320), nullable=True),
    sa.Column("lead_phone", sa.String(64), nullable=True),
    sa.Column("location", sa.String(512), nullable=True),
    sa.Column("bid_due_on", sa.Date(), nullable=True),
    sa.Column("rfp_id", sa.String(32), nullable=True),
    sa.Column("rfp_url", sa.String(1024), nullable=True),
    sa.Column("headline", sa.String(512), nullable=True),
    sa.Column("parsed_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


def upgrade() -> None:
    for col in _COLUMNS:
        op.add_column("bid_invites", col)
    op.create_index(
        "ix_bid_invites_tenant_due", "bid_invites", ["tenant_id", "bid_due_on"]
    )


def downgrade() -> None:
    op.drop_index("ix_bid_invites_tenant_due", table_name="bid_invites")
    for col in reversed(_COLUMNS):
        op.drop_column("bid_invites", col.name)
