"""Cyber scope analyses + opportunity_scores cyber columns.

Revision ID: 0028_cyber_scope
Revises: 0027_high_moat_scoring
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_cyber_scope"
down_revision: str | Sequence[str] | None = "0027_high_moat_scoring"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cyber_scope_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_name", sa.String(512), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("source_hash", sa.String(64), nullable=True),
        sa.Column(
            "scan_pass",
            sa.String(32),
            server_default=sa.text("'description_only'"),
            nullable=False,
        ),
        sa.Column("parser_version", sa.String(16), nullable=False),
        sa.Column("overall_cyber_likelihood", sa.String(16), nullable=False),
        sa.Column("recommended_pursuit_model", sa.String(32), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "detected_categories_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "top_signals_json",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "hidden_scope_indicators_json",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "missing_requirements_json",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "suggested_actions_json",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence_snippets_json",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "ufgs_center_of_gravity",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "ufgs_tier_1_hit",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities_raw.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "opportunity_id", name="uq_cyber_scope_tenant_opp"
        ),
    )
    op.create_index(
        "ix_cyber_scope_tenant_likelihood",
        "cyber_scope_analyses",
        ["tenant_id", "overall_cyber_likelihood", "score"],
    )

    op.add_column(
        "opportunity_scores",
        sa.Column("cyber_scope_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("cyber_scope_likelihood", sa.String(16), nullable=True),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("cyber_scope_pursuit_model", sa.String(32), nullable=True),
    )
    op.add_column(
        "opportunity_scores",
        sa.Column("cyber_scope_flags", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("opportunity_scores", "cyber_scope_flags")
    op.drop_column("opportunity_scores", "cyber_scope_pursuit_model")
    op.drop_column("opportunity_scores", "cyber_scope_likelihood")
    op.drop_column("opportunity_scores", "cyber_scope_score")
    op.drop_index("ix_cyber_scope_tenant_likelihood", table_name="cyber_scope_analyses")
    op.drop_table("cyber_scope_analyses")
