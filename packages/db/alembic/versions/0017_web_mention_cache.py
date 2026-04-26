"""web_mention_cache — SerpAPI per-opportunity cache.

Revision ID: 0017_web_mention_cache
Revises: 0016_library_import_jobs
Create Date: 2026-04-26

Sprint 19. SerpAPI charges per query, so opportunity-detail "Web
mentions" panels must cache. Keyed by (tenant_id, opportunity_id,
query_kind) so we can refresh each kind (program-name, incumbent,
agency-news) independently. 7-day TTL enforced by the API at read time.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0017_web_mention_cache"
down_revision: str | Sequence[str] | None = "0016_library_import_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "web_mention_cache",
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
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_kind", sa.String(32), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("results", JSONB(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("engine", sa.String(32), nullable=False, server_default="google"),
        sa.Column(
            "fetched_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "opportunity_id",
            "query_kind",
            name="uq_web_mention_cache_tenant_opp_kind",
        ),
    )


def downgrade() -> None:
    op.drop_table("web_mention_cache")
