"""SBIR topic feed populated by the Apify ingest.

Revision ID: 0031_sbir_topics
Revises: 0030_sbir_submissions

Shared (untenanted) table for the SBIR Topics page at /sbir. Mirrors the
agency_events pattern. Unique (source, topic_number) so the same topic
can't be double-ingested from the same source.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_sbir_topics"
down_revision: str | Sequence[str] | None = "0030_sbir_submissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sbir_topics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("topic_number", sa.String(64), nullable=False),
        sa.Column("title", sa.String(1024), nullable=True),
        sa.Column("component", sa.String(64), nullable=True),
        sa.Column("program", sa.String(16), nullable=True),
        sa.Column("phase", sa.String(16), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column("prerelease_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("open_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("close_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column(
            "technology_areas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "modernization_priorities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("itar_export_status", sa.String(32), nullable=True),
        sa.Column("phase_i_ceiling", sa.Integer(), nullable=True),
        sa.Column("phase_i_duration_months", sa.Integer(), nullable=True),
        sa.Column(
            "raw",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("apify_run_id", sa.String(64), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source", "topic_number", name="uq_sbir_topics_source_topic"
        ),
    )
    op.create_index(
        "ix_sbir_topics_status_close",
        "sbir_topics",
        ["status", "close_date"],
    )
    op.create_index("ix_sbir_topics_component", "sbir_topics", ["component"])


def downgrade() -> None:
    op.drop_index("ix_sbir_topics_component", table_name="sbir_topics")
    op.drop_index("ix_sbir_topics_status_close", table_name="sbir_topics")
    op.drop_table("sbir_topics")
