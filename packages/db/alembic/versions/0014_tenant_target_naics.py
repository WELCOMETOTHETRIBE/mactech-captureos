"""tenants.target_naics

Revision ID: 0014_tenant_target_naics
Revises: 0013_tenant_onboarding
Create Date: 2026-04-25

Phase 3 Week 14 (UX Sprint 9). NAICS codes the tenant wants opportunities
scored against. Set by the onboarding wizard's NAICS picker, defaulted
from the SAM Entity API result.

When null, the scoring engine falls back to the seed-config NAICS list
(the existing behaviour for MacTech). When set, it overrides per-tenant.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0014_tenant_target_naics"
down_revision: str | Sequence[str] | None = "0013_tenant_onboarding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("target_naics", ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "target_naics")
