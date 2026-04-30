"""tenants: SAM registration + exclusions verification columns.

Revision ID: 0026_tenant_sam_verification
Revises: 0025_saved_search_delivery
Create Date: 2026-04-29

Closes B1, B2, and B3-on-self from CaptureOS_Requirements.md. The
``mactech.tenant.verify_sam`` worker (daily) now keeps these columns
fresh by hitting SAM Entity API + SAM Exclusions API for every tenant
that has a UEI on file.

Columns:
* ``sam_registration_status`` — ``active`` / ``expired`` / ``invalid`` /
  null (never verified). Mirrors the SAM Entity ``registrationStatus``.
* ``sam_registration_date`` — when the entity first registered.
* ``sam_registration_expires_at`` — annual renewal deadline.
* ``sam_registration_last_checked_at`` — when CaptureOS last refreshed.
* ``is_excluded`` — true if the tenant's UEI shows up on the federal
  exclusions / debarment list. Hard bidding blocker.
* ``exclusions_record_count`` — how many exclusion records returned;
  usually 0 or 1.
* ``exclusions_last_checked_at`` — when CaptureOS last refreshed.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_tenant_sam_verification"
down_revision: str | Sequence[str] | None = "0025_saved_search_delivery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("sam_registration_status", sa.String(16), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("sam_registration_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("sam_registration_expires_at", sa.Date(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "sam_registration_last_checked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "is_excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "exclusions_record_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "exclusions_last_checked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "exclusions_last_checked_at")
    op.drop_column("tenants", "exclusions_record_count")
    op.drop_column("tenants", "is_excluded")
    op.drop_column("tenants", "sam_registration_last_checked_at")
    op.drop_column("tenants", "sam_registration_expires_at")
    op.drop_column("tenants", "sam_registration_date")
    op.drop_column("tenants", "sam_registration_status")
