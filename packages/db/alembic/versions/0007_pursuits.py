"""pursuits table

Revision ID: 0007_pursuits
Revises: 0006_clerk_and_rls
Create Date: 2026-04-24

Phase 2 Week 7. Adds the capture pipeline kanban table.

One row per (tenant, opportunity). Stages: lead → qualify → pursue →
propose → submit → won/lost. Free transitions allowed (no enforced DAG)
because pursuits drop back to a prior stage all the time in real BD work.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_pursuits"
down_revision: str | Sequence[str] | None = "0006_clerk_and_rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pursuits",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_founder_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stage", sa.String(16), nullable=False, server_default="lead"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column(
            "last_stage_change_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id", "opportunity_id", name="uq_pursuits_tenant_opp"
        ),
        sa.CheckConstraint(
            "stage in ('lead','qualify','pursue','propose','submit','won','lost')",
            name="ck_pursuits_stage",
        ),
    )
    op.create_index(
        "ix_pursuits_tenant_stage", "pursuits", ["tenant_id", "stage"]
    )
    op.create_index("ix_pursuits_owner", "pursuits", ["owner_founder_id"])


def downgrade() -> None:
    op.drop_index("ix_pursuits_owner", table_name="pursuits")
    op.drop_index("ix_pursuits_tenant_stage", table_name="pursuits")
    op.drop_table("pursuits")
