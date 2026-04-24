"""enrichment tables: opportunities_enriched + awards_history + exclusions_cache

Revision ID: 0003_enrichment_tables
Revises: 0002_opportunities_raw
Create Date: 2026-04-24

Phase 1 Week 3. Schemas mirror docs/SCHEMA.md. opportunities_enriched is
1:1 with opportunities_raw (single derived row per opp). awards_history
is the persistent cache of relevant USASpending + FPDS awards we've seen,
keyed by (source, award_id). exclusions_cache is the tenant-agnostic
SAM Exclusions cache, keyed by UEI with a 24h TTL applied at query time.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_enrichment_tables"
down_revision: str | Sequence[str] | None = "0002_opportunities_raw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunities_enriched",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "opportunity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("incumbent_uei", sa.String(), nullable=True),
        sa.Column("incumbent_name", sa.String(), nullable=True),
        sa.Column("incumbent_contract_id", sa.String(), nullable=True),
        sa.Column("incumbent_end_date", sa.Date(), nullable=True),
        sa.Column("incumbent_award_amount", sa.Numeric(), nullable=True),
        sa.Column("requirements", postgresql.JSONB(), nullable=True),
        sa.Column("naics_match_notes", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(),
            nullable=False,
            server_default=sa.text("'usaspending'"),
        ),
        sa.Column(
            "enriched_at",
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
    )
    op.create_index(
        "idx_opp_enriched_incumbent_uei",
        "opportunities_enriched",
        ["incumbent_uei"],
    )

    op.create_table(
        "awards_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("award_id", sa.String(), nullable=False),
        sa.Column("piid", sa.String(), nullable=True),
        sa.Column("recipient_uei", sa.String(), nullable=True),
        sa.Column("recipient_name", sa.String(), nullable=True),
        sa.Column("recipient_hash", sa.String(), nullable=True),
        sa.Column("awarding_agency", sa.String(), nullable=True),
        sa.Column("awarding_subagency", sa.String(), nullable=True),
        sa.Column(
            "naics_code",
            sa.String(),
            sa.ForeignKey("naics_codes.code"),
            nullable=True,
        ),
        sa.Column("award_type", sa.String(), nullable=True),
        sa.Column("obligated_amount", sa.Numeric(), nullable=True),
        sa.Column("base_and_all_options_value", sa.Numeric(), nullable=True),
        sa.Column("period_of_performance_start", sa.Date(), nullable=True),
        sa.Column("period_of_performance_current_end", sa.Date(), nullable=True),
        sa.Column("period_of_performance_potential_end", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("source", "award_id", name="uq_awards_history_source_id"),
    )
    op.create_index("idx_award_recipient", "awards_history", ["recipient_uei"])
    op.create_index(
        "idx_award_naics_agency", "awards_history", ["naics_code", "awarding_agency"]
    )
    op.create_index(
        "idx_award_end_date", "awards_history", ["period_of_performance_current_end"]
    )

    op.create_table(
        "exclusions_cache",
        sa.Column("uei", sa.String(), primary_key=True),
        sa.Column("is_excluded", sa.Boolean(), nullable=False),
        sa.Column("exclusion_details", postgresql.JSONB(), nullable=True),
        sa.Column(
            "checked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("exclusions_cache")
    op.drop_index("idx_award_end_date", table_name="awards_history")
    op.drop_index("idx_award_naics_agency", table_name="awards_history")
    op.drop_index("idx_award_recipient", table_name="awards_history")
    op.drop_table("awards_history")
    op.drop_index("idx_opp_enriched_incumbent_uei", table_name="opportunities_enriched")
    op.drop_table("opportunities_enriched")
