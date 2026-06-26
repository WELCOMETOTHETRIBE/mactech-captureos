"""SBIR topic DSIP enrichment columns.

Revision ID: 0032_sbir_topic_dsip_enrichment
Revises: 0031_sbir_topics

Adds columns populated by the Apify Playwright DSIP lookup so the
submitter pre-fill can use the official topic text + PDF when present.
Sbirdashboard remains the cheap discovery surface; DSIP is the lazy
enrichment surface fired when the user picks a topic.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_sbir_topic_dsip_enrichment"
down_revision: str | Sequence[str] | None = "0031_sbir_topics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sbir_topics",
        sa.Column("dsip_enriched_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column("sbir_topics", sa.Column("dsip_tpoc", sa.String(512), nullable=True))
    op.add_column(
        "sbir_topics", sa.Column("dsip_pdf_url", sa.String(1024), nullable=True)
    )
    op.add_column("sbir_topics", sa.Column("dsip_pdf_text", sa.Text(), nullable=True))
    op.add_column(
        "sbir_topics", sa.Column("dsip_apify_run_id", sa.String(64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("sbir_topics", "dsip_apify_run_id")
    op.drop_column("sbir_topics", "dsip_pdf_text")
    op.drop_column("sbir_topics", "dsip_pdf_url")
    op.drop_column("sbir_topics", "dsip_tpoc")
    op.drop_column("sbir_topics", "dsip_enriched_at")
