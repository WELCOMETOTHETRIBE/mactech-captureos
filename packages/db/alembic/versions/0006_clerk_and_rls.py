"""tenants.clerk_org_id

Revision ID: 0006_clerk_and_rls
Revises: 0005_founder_email
Create Date: 2026-04-24

Phase 2 Week 5. Adds the Clerk Organization mapping column to tenants.

Originally this migration was going to ENABLE + FORCE row-level
security on tenant-scoped tables. Decision deferred: with one tenant
(MacTech) in Phase 1–3, cross-tenant leak risk is zero, and activating
RLS now would force every background worker to SET LOCAL app.tenant_id
without preventing any real risk. RLS will be flipped on in Phase 4
alongside a non-owner DB user for the API service, when external
customer onboarding starts. The application layer continues to filter
by tenant_id in the meantime — the same pattern Phase 1 has used since
Week 1.

The migration name `0006_clerk_and_rls` is preserved so the next
migration that does activate RLS reads as a follow-up rather than a
parallel concern.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_clerk_and_rls"
down_revision: str | Sequence[str] | None = "0005_founder_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("clerk_org_id", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_tenants_clerk_org_id", "tenants", ["clerk_org_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_tenants_clerk_org_id", "tenants", type_="unique")
    op.drop_column("tenants", "clerk_org_id")
