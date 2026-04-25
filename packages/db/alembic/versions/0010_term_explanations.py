"""term_explanations cache

Revision ID: 0010_term_explanations
Revises: 0009_proposal_drafts
Create Date: 2026-04-25

Phase 3 Week 10. Caches plain-English explanations of jargon terms
(NAICS codes, set-aside codes, notice types, score components) so the
"Explain this" right rail on the opportunity detail page doesn't spend
tokens on every click.

Cache key is (slug, prompt_version). prompt_version bump invalidates
without a deletion sweep.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0010_term_explanations"
down_revision: str | Sequence[str] | None = "0009_proposal_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "term_explanations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "first_requested_by_tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "slug", "prompt_version", name="uq_term_explanations_slug_version"
        ),
    )
    op.create_index(
        "ix_term_explanations_slug", "term_explanations", ["slug"]
    )


def downgrade() -> None:
    op.drop_index("ix_term_explanations_slug", table_name="term_explanations")
    op.drop_table("term_explanations")
