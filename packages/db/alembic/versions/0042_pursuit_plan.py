"""Pursuit recommendations + dated actions.

Revision ID: 0042_pursuit_plan
Revises: 0041_prime_targets

Slice 6. The engine's regenerable pursuit plan (one per tenant+opportunity) and
its ordered, dated next actions — the "who does what, by when" answer.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0042_pursuit_plan"
down_revision: str | Sequence[str] | None = "0041_prime_targets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pursuit_recommendations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pursuit_id", UUID(as_uuid=True), sa.ForeignKey("pursuits.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pursuit_lane", sa.String(40), nullable=False),
        sa.Column("executive_decision", sa.Text, nullable=False),
        sa.Column("why_this_is_real", sa.Text, nullable=True),
        sa.Column("mactech_work_package", sa.Text, nullable=True),
        sa.Column("blocking_issues", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("prime_target_names", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("recommended_owner_slug", sa.String(64), nullable=True),
        sa.Column("decision_deadline", sa.Date, nullable=True),
        sa.Column("response_deadline", sa.Date, nullable=True),
        sa.Column("confidence", sa.String(16), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("generated_by", sa.String(32), nullable=False, server_default=sa.text("'deterministic'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "opportunity_id", name="uq_pursuit_recs_tenant_opp"),
    )
    op.create_index("ix_pursuit_recs_opp", "pursuit_recommendations", ["tenant_id", "opportunity_id"])

    op.create_table(
        "pursuit_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_id", UUID(as_uuid=True), sa.ForeignKey("pursuit_recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("owner_founder_slug", sa.String(64), nullable=True),
        sa.Column("due_at", sa.Date, nullable=True),
        sa.Column("purpose", sa.Text, nullable=True),
        sa.Column("completion_criteria", sa.Text, nullable=True),
        sa.Column("dependency", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pursuit_actions_rec", "pursuit_actions", ["recommendation_id"])


def downgrade() -> None:
    op.drop_index("ix_pursuit_actions_rec", table_name="pursuit_actions")
    op.drop_table("pursuit_actions")
    op.drop_index("ix_pursuit_recs_opp", table_name="pursuit_recommendations")
    op.drop_table("pursuit_recommendations")
