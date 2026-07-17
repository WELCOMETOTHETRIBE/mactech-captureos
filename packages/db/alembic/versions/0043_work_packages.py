"""LLM-adjudicated work packages.

Revision ID: 0043_work_packages
Revises: 0042_pursuit_plan

Slice 5. opportunity_work_packages holds the LLM decomposition of an opportunity
into bounded units, each backed by validated evidence ids, with model/prompt/
pack provenance.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0043_work_packages"
down_revision: str | Sequence[str] | None = "0042_pursuit_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_work_packages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("scope_category", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("deliverables", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("required_roles", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("required_credentials", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("mactech_role", sa.String(24), nullable=False, server_default=sa.text("'sub'")),
        sa.Column("confidence", sa.String(16), nullable=False, server_default=sa.text("'low'")),
        sa.Column("evidence_ids", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column("knowledge_pack_version", sa.String(128), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_work_packages_opp", "opportunity_work_packages", ["tenant_id", "opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_work_packages_opp", table_name="opportunity_work_packages")
    op.drop_table("opportunity_work_packages")
