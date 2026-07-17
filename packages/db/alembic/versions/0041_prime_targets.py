"""Prime-target intelligence.

Revision ID: 0041_prime_targets
Revises: 0040_decision_engine

Slice 7. ``prime_targets`` (SHARED, no tenant_id) is a discovery cache of
companies MacTech could team under, keyed by uei-or-normalized-name.
``opportunity_prime_targets`` is the tenant-scoped link with rationale/evidence.
Populating these lets the decision engine flip SUB_TO_PRIME_NOT_YET_IDENTIFIED
to SUB_TO_IDENTIFIED_PRIME.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "0041_prime_targets"
down_revision: str | Sequence[str] | None = "0040_decision_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prime_targets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("uei", sa.String(32), nullable=True),
        sa.Column("cage_code", sa.String(16), nullable=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False, server_default=sa.text("'historical_awardee'")),
        sa.Column("agencies", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("naics_codes", ARRAY(sa.String), nullable=True),
        sa.Column("recent_award_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("total_recent_award_amount", sa.Numeric, nullable=True),
        sa.Column("award_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("contact", JSONB, nullable=True),
        sa.Column("source", sa.String(24), nullable=False, server_default=sa.text("'usaspending'")),
        sa.Column("teaming_partner_id", UUID(as_uuid=True), sa.ForeignKey("teaming_partners.id", ondelete="SET NULL"), nullable=True),
        sa.Column("refreshed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dedupe_key", name="uq_prime_targets_dedupe_key"),
    )

    op.create_table(
        "opportunity_prime_targets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prime_target_id", UUID(as_uuid=True), sa.ForeignKey("prime_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False, server_default="0"),
        sa.Column("why_target", sa.Text, nullable=True),
        sa.Column("recommended_contact_role", sa.String(128), nullable=True),
        sa.Column("relationship_status", sa.String(24), nullable=False, server_default=sa.text("'none'")),
        sa.Column("outreach_deadline", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=False, server_default=sa.text("'possible'")),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "opportunity_id", "prime_target_id", name="uq_opp_prime_targets_link"),
    )
    op.create_index("ix_opp_prime_targets_opp", "opportunity_prime_targets", ["tenant_id", "opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_opp_prime_targets_opp", table_name="opportunity_prime_targets")
    op.drop_table("opportunity_prime_targets")
    op.drop_table("prime_targets")
