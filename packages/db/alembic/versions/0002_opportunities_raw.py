"""opportunities_raw + ingestion_state + pgvector + pg_trgm

Revision ID: 0002_opportunities_raw_and_ingestion_state
Revises: 0001_initial_skeleton
Create Date: 2026-04-24

Phase 1 Week 2: SAM.gov Opportunities ingestion lands here. Embedding
column is created but unindexed — pgvector ivfflat index is added in
Week 3 once embeddings populate. Description text column is also created
but unfilled — chained noticedesc fetches happen Week 2 if budget allows,
Week 3 otherwise.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_opportunities_raw_and_ingestion_state"
down_revision: str | Sequence[str] | None = "0001_initial_skeleton"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "opportunities_raw",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("notice_type", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description_url", sa.String(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("solicitation_number", sa.String(), nullable=True),
        sa.Column("agency", sa.String(), nullable=True),
        sa.Column("subagency", sa.String(), nullable=True),
        sa.Column("office", sa.String(), nullable=True),
        sa.Column(
            "naics_code",
            sa.String(),
            sa.ForeignKey("naics_codes.code"),
            nullable=True,
        ),
        sa.Column("set_aside", sa.String(), nullable=True),
        sa.Column("estimated_value_low", sa.Numeric(), nullable=True),
        sa.Column("estimated_value_high", sa.Numeric(), nullable=True),
        sa.Column("posted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("response_deadline", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("place_of_performance", postgresql.JSONB(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "embedding",
            postgresql.ARRAY(sa.REAL),  # placeholder; switched to vector(1024) below
            nullable=True,
        ),
        sa.Column("hash", sa.String(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source", "source_id", name="uq_opportunities_raw_source_id"),
    )

    # Replace the placeholder embedding column with a real pgvector(1024).
    # Doing it this way (drop+add) keeps SQLAlchemy reflection clean without
    # requiring the pgvector dialect to be loaded inside Alembic env.
    op.execute("ALTER TABLE opportunities_raw DROP COLUMN embedding")
    op.execute("ALTER TABLE opportunities_raw ADD COLUMN embedding vector(1024)")

    op.create_index("idx_opp_naics", "opportunities_raw", ["naics_code"])
    op.create_index("idx_opp_agency", "opportunities_raw", ["agency"])
    op.create_index(
        "idx_opp_posted",
        "opportunities_raw",
        [sa.text("posted_at DESC")],
    )
    op.create_index("idx_opp_setaside", "opportunities_raw", ["set_aside"])
    op.create_index(
        "idx_opp_response_deadline",
        "opportunities_raw",
        ["response_deadline"],
    )
    op.execute(
        "CREATE INDEX idx_opp_description_trgm "
        "ON opportunities_raw USING gin (description_text gin_trgm_ops)"
    )
    # Embedding ivfflat index is created in Week 3 when we have rows to train it on.

    op.create_table(
        "ingestion_state",
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("last_run_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_cursor", sa.String(), nullable=True),
        sa.Column("last_status", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "ingested_count_lifetime",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("source", "key"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_state")
    op.drop_index("idx_opp_description_trgm", table_name="opportunities_raw")
    op.drop_index("idx_opp_response_deadline", table_name="opportunities_raw")
    op.drop_index("idx_opp_setaside", table_name="opportunities_raw")
    op.drop_index("idx_opp_posted", table_name="opportunities_raw")
    op.drop_index("idx_opp_agency", table_name="opportunities_raw")
    op.drop_index("idx_opp_naics", table_name="opportunities_raw")
    op.drop_table("opportunities_raw")
    # pgvector + pg_trgm extensions left in place — other tables may use them later.
