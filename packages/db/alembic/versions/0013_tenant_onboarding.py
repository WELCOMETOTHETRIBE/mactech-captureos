"""tenants.set_aside_certifications + onboarding_completed_at

Revision ID: 0013_tenant_onboarding
Revises: 0012_agency_intel
Create Date: 2026-04-25

Phase 3 Week 14 (UX Sprint 8). Two columns added to `tenants`:

  set_aside_certifications  text[] — SDVOSB, 8(a), HUBZone, WOSB, etc.
                                     auto-filled from SAM Entity API.
  onboarding_completed_at   timestamptz null — set when the wizard
                                     completes; null signals "needs
                                     onboarding" to the dashboard banner.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0013_tenant_onboarding"
down_revision: str | Sequence[str] | None = "0012_agency_intel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "set_aside_certifications",
            ARRAY(sa.String()),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "onboarding_completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "onboarding_completed_at")
    op.drop_column("tenants", "set_aside_certifications")
