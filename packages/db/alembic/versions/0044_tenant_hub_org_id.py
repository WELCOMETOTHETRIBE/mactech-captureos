"""Cache the Hub organization id on tenants.

Revision ID: 0044_tenant_hub_org_id
Revises: 0043_work_packages

The bizops Directory (shared company address book) keys tenants by the Hub's
CustomerOrganization id, while Capture keys them by clerk_org_id. The ICC
access endpoint returns both, so the Directory routes resolve the Hub id once
per tenant and cache it here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_tenant_hub_org_id"
down_revision: str | Sequence[str] | None = "0043_work_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("hub_org_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "hub_org_id")
