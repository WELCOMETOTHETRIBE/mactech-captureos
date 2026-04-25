"""past_performance + teaming_partners

Revision ID: 0008_library_tables
Revises: 0007_pursuits
Create Date: 2026-04-25

Phase 2 Week 8. Adds the two catalogue tables that power the
proposal/Sources Sought drafter in Phase 3.

past_performance: prior contract narratives the firm cites in capability
responses. One row per cited engagement.

teaming_partners: relationship roster — primes/subs MacTech might team
with on multi-vendor pursuits. Status flag separates active partners
from archived/inactive ones.

Both tables are tenant-scoped with CASCADE on tenant delete.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision: str = "0008_library_tables"
down_revision: str | Sequence[str] | None = "0007_pursuits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "past_performance",
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
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("customer_agency", sa.String(255), nullable=True),
        sa.Column("customer_office", sa.String(255), nullable=True),
        sa.Column("contract_number", sa.String(64), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="prime"),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("contract_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("naics_code", sa.String(8), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("keywords", ARRAY(sa.String()), nullable=True),
        sa.Column("related_capability_slugs", ARRAY(sa.String()), nullable=True),
        sa.Column("related_founder_slugs", ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "title", name="uq_past_perf_tenant_title"),
        sa.CheckConstraint(
            "role in ('prime','sub','joint_venture','individual')",
            name="ck_past_perf_role",
        ),
    )
    op.create_index("ix_past_perf_tenant", "past_performance", ["tenant_id"])

    op.create_table(
        "teaming_partners",
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("uei", sa.String(16), nullable=True),
        sa.Column("cage_code", sa.String(8), nullable=True),
        sa.Column("capabilities", ARRAY(sa.String()), nullable=True),
        sa.Column("naics_codes", ARRAY(sa.String()), nullable=True),
        sa.Column("set_aside_certifications", ARRAY(sa.String()), nullable=True),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "name", name="uq_teaming_tenant_name"),
    )
    op.create_index(
        "ix_teaming_tenant_status", "teaming_partners", ["tenant_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_teaming_tenant_status", table_name="teaming_partners")
    op.drop_table("teaming_partners")
    op.drop_index("ix_past_perf_tenant", table_name="past_performance")
    op.drop_table("past_performance")
