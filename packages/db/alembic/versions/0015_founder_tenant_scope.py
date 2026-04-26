"""tenant-scope founders

Revision ID: 0015_founder_tenant_scope
Revises: 0014_tenant_target_naics
Create Date: 2026-04-25

Phase 3 Week 15 (Sprint 11). Backfills `founders.tenant_id` from the
single MacTech tenant, then enforces the column NOT NULL with a CASCADE
foreign key. Drops the global `founders_slug_key` unique on `slug`,
replacing it with `uq_founders_tenant_slug` on `(tenant_id, slug)` so
two tenants can each have a founder with the same slug.

Pre-condition: the single existing tenant has `slug = 'mactech'`. If
the migration runs against a database with multiple tenants but
no `tenant_id` on founders, the backfill UPDATE will assign all
founders to MacTech — that's wrong for multi-tenant data, correct
for our current single-tenant reality. (Documented; future migration
would handle multi-tenant backfill via Clerk org id mapping.)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0015_founder_tenant_scope"
down_revision: str | Sequence[str] | None = "0014_tenant_target_naics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add nullable column.
    op.add_column(
        "founders",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
    )

    # 2. Backfill from the single existing tenant. The `slug = 'mactech'`
    #    assumption is documented in the module docstring.
    op.execute(
        "update founders set tenant_id = "
        "(select id from tenants where slug = 'mactech') "
        "where tenant_id is null"
    )

    # 3. Verify backfill completed (defensive; raises if any null left).
    op.execute(
        "do $$ begin "
        "if exists (select 1 from founders where tenant_id is null) then "
        "raise exception 'founders rows with null tenant_id remain after backfill'; "
        "end if; end $$;"
    )

    # 4. Lock down: NOT NULL + FK.
    op.alter_column("founders", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_founders_tenant",
        "founders",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 5. Swap the slug unique constraint from global to per-tenant.
    op.execute("alter table founders drop constraint if exists founders_slug_key")
    op.create_unique_constraint(
        "uq_founders_tenant_slug", "founders", ["tenant_id", "slug"]
    )

    op.create_index("ix_founders_tenant_id", "founders", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_founders_tenant_id", table_name="founders")
    op.drop_constraint("uq_founders_tenant_slug", "founders", type_="unique")
    # Restore the global slug unique. If duplicate slugs exist across
    # tenants this will fail — that's the correct behavior.
    op.create_unique_constraint("founders_slug_key", "founders", ["slug"])
    op.drop_constraint("fk_founders_tenant", "founders", type_="foreignkey")
    op.drop_column("founders", "tenant_id")
