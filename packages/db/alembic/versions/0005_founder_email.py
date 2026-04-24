"""founders.email + founders.digest_enabled

Revision ID: 0005_founder_email
Revises: 0004_scoring_tables
Create Date: 2026-04-24

Phase 1 Week 4 stretch: lets the digest worker know where to send each
founder's daily digest and whether to send it at all. digest_enabled
defaults to true; flip to false on a founder during onboarding.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_founder_email"
down_revision: str | Sequence[str] | None = "0004_scoring_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("founders", sa.Column("email", sa.String(), nullable=True))
    op.add_column(
        "founders",
        sa.Column(
            "digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("founders", "digest_enabled")
    op.drop_column("founders", "email")
