"""Bid invite → pipeline linking: group_key + opportunity_id.

Revision ID: 0035_bid_invite_pipeline_link
Revises: 0034_bid_invite_parsing

group_key is the normalized project identity (set at ingest/reparse);
opportunity_id points at the buildingconnected-sourced
opportunities_raw row once the project is promoted into the pipeline.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035_bid_invite_pipeline_link"
down_revision: str | Sequence[str] | None = "0034_bid_invite_parsing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("bid_invites", sa.Column("group_key", sa.String(512), nullable=True))
    op.add_column(
        "bid_invites",
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_bid_invites_opportunity",
        "bid_invites",
        "opportunities_raw",
        ["opportunity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_bid_invites_tenant_group", "bid_invites", ["tenant_id", "group_key"]
    )


def downgrade() -> None:
    op.drop_index("ix_bid_invites_tenant_group", table_name="bid_invites")
    op.drop_constraint("fk_bid_invites_opportunity", "bid_invites", type_="foreignkey")
    op.drop_column("bid_invites", "opportunity_id")
    op.drop_column("bid_invites", "group_key")
