"""scoring tables: opportunity_scores + capability_statements

Revision ID: 0004_scoring_tables
Revises: 0003_enrichment_tables
Create Date: 2026-04-24

Phase 1 Week 4. opportunity_scores is tenant-scoped (one score per
(tenant, opp)) so the same opportunity can score differently against
different MacTech tenants once external customers come online.
capability_statements is tenant-scoped MacTech-owned data; embeddings
populate via the same Voyage worker that does opportunities_raw.

HNSW indexes (pgvector 0.8 default, no tuning) instead of the ivfflat
indicated in docs/SCHEMA.md — HNSW handles small datasets without a
training pass, which is the right tradeoff at our row count.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_scoring_tables"
down_revision: str | Sequence[str] | None = "0003_enrichment_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capability_statements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("related_naics", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("related_founders", postgresql.JSONB(), nullable=True),
        sa.Column("artifact_s3_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
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
        sa.UniqueConstraint("tenant_id", "title", name="uq_capability_tenant_title"),
    )
    # pgvector column added separately because the alembic op.create_table
    # path doesn't know about the vector type without the pgvector dialect.
    op.execute("ALTER TABLE capability_statements ADD COLUMN embedding vector(1024)")
    op.execute(
        "CREATE INDEX idx_capstmt_embedding "
        "ON capability_statements USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX idx_opp_embedding_hnsw "
        "ON opportunities_raw USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "opportunity_scores",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=False),
        sa.Column(
            "assigned_founder_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("founders.id"),
            nullable=True,
        ),
        sa.Column("why_it_matters", sa.Text(), nullable=True),
        sa.Column("why_it_matters_model", sa.String(), nullable=True),
        sa.Column(
            "scored_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id", "opportunity_id", name="uq_scores_tenant_opp"
        ),
    )
    op.create_index(
        "idx_scores_tenant_score",
        "opportunity_scores",
        ["tenant_id", sa.text("score DESC")],
    )
    op.create_index(
        "idx_scores_assigned_founder",
        "opportunity_scores",
        ["tenant_id", "assigned_founder_id", sa.text("score DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_scores_assigned_founder", table_name="opportunity_scores")
    op.drop_index("idx_scores_tenant_score", table_name="opportunity_scores")
    op.drop_table("opportunity_scores")
    op.execute("DROP INDEX IF EXISTS idx_opp_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS idx_capstmt_embedding")
    op.drop_table("capability_statements")
