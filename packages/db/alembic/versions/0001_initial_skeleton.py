"""initial skeleton: tenants, users, founders, naics, saved_searches

Revision ID: 0001_initial_skeleton
Revises:
Create Date: 2026-04-24

Phase 1 Week 1 tables only. opportunities_raw, pursuits, and the rest
arrive in Week 2+ per docs/ROADMAP.md.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_skeleton"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False, server_default=sa.text("'scout'")),
        sa.Column("uei", sa.String(), nullable=True),
        sa.Column("cage_code", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "naics_codes",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("size_standard", sa.String(), nullable=True),
        sa.Column("mactech_tier", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "founders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("pillar", sa.String(), nullable=False),
        sa.Column("bio", sa.String(), nullable=True),
        sa.Column("areas_of_expertise", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("clerk_user_id", sa.String(), unique=True, nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=False, server_default=sa.text("'member'")),
        sa.Column(
            "founder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("founders.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_users_tenant", "users", ["tenant_id"])

    op.create_table(
        "founder_naics_matrix",
        sa.Column(
            "founder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("founders.id"),
            primary_key=True,
        ),
        sa.Column(
            "naics_code",
            sa.String(),
            sa.ForeignKey("naics_codes.code"),
            primary_key=True,
        ),
        sa.Column("affinity", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("idx_fnm_naics", "founder_naics_matrix", ["naics_code"])

    op.create_table(
        "saved_searches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "owner_founder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("founders.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False),
        sa.Column(
            "alert_threshold", sa.Integer(), nullable=False, server_default=sa.text("70")
        ),
        sa.Column(
            "alert_cadence",
            sa.String(),
            nullable=False,
            server_default=sa.text("'daily'"),
        ),
        sa.Column(
            "alert_channels",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"email\"]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_saved_searches_tenant", "saved_searches", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("idx_saved_searches_tenant", table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_index("idx_fnm_naics", table_name="founder_naics_matrix")
    op.drop_table("founder_naics_matrix")
    op.drop_index("idx_users_tenant", table_name="users")
    op.drop_table("users")
    op.drop_table("founders")
    op.drop_table("naics_codes")
    op.drop_table("tenants")
