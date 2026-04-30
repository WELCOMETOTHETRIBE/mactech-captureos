"""Per-pursuit asset links + win themes/discriminators + evaluation tables.

Revision ID: 0023_pursuit_links_evaluation
Revises: 0022_solicitation_extractions
Create Date: 2026-04-29

Catch-up sprint to fill the gaps the Capture Package schema published
but the data model couldn't yet back:

* pursuits.win_themes + pursuits.discriminators — JSONB arrays the
  capture lead curates for the proposal team.

* pursuit_past_performance / pursuit_key_personnel /
  pursuit_teaming_partners — junction tables that record which library
  records the user has selected for a specific pursuit. Light fields
  per row: optional role, sort order, created_at. Tenant denormalized
  for RLS-style scoping; cascades on parent deletes.

* evaluation_pass_fail_items + evaluation_scored_factors — children of
  solicitation_extractions, holding the Section M items extracted in
  the same Claude pass that produces compliance + requirements. Two
  tables because their shapes differ enough that one polymorphic table
  would be uglier than two clean ones.

Solicitation_extractions also gets evaluation_count for parity with the
existing compliance_count + requirements_count columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0023_pursuit_links_evaluation"
down_revision: str | Sequence[str] | None = "0022_solicitation_extractions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── pursuits: win_themes + discriminators ──────────────────────
    op.add_column(
        "pursuits",
        sa.Column(
            "win_themes",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "pursuits",
        sa.Column(
            "discriminators",
            JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )

    # ── pursuit_past_performance ───────────────────────────────────
    op.create_table(
        "pursuit_past_performance",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "pursuit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pursuits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "past_performance_id",
            UUID(as_uuid=True),
            sa.ForeignKey("past_performance.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "pursuit_id",
            "past_performance_id",
            name="uq_pursuit_past_performance_pursuit_pp",
        ),
    )
    op.create_index(
        "ix_pursuit_past_performance_tenant_pursuit",
        "pursuit_past_performance",
        ["tenant_id", "pursuit_id", "sort_order"],
    )

    # ── pursuit_key_personnel (founder = key person in V1) ─────────
    op.create_table(
        "pursuit_key_personnel",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "pursuit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pursuits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "founder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "pursuit_id", "founder_id", name="uq_pursuit_key_personnel_pursuit_founder"
        ),
    )
    op.create_index(
        "ix_pursuit_key_personnel_tenant_pursuit",
        "pursuit_key_personnel",
        ["tenant_id", "pursuit_id", "sort_order"],
    )

    # ── pursuit_teaming_partners ───────────────────────────────────
    op.create_table(
        "pursuit_teaming_partners",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "pursuit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pursuits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "teaming_partner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("teaming_partners.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "pursuit_id",
            "teaming_partner_id",
            name="uq_pursuit_teaming_partners_pursuit_partner",
        ),
    )
    op.create_index(
        "ix_pursuit_teaming_partners_tenant_pursuit",
        "pursuit_teaming_partners",
        ["tenant_id", "pursuit_id", "sort_order"],
    )

    # ── evaluation_pass_fail_items + evaluation_scored_factors ─────
    op.create_table(
        "evaluation_pass_fail_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "extraction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
            nullable=False,
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
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("source_citation", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evaluation_pass_fail_tenant_opp_sort",
        "evaluation_pass_fail_items",
        ["tenant_id", "opportunity_id", "sort_order"],
    )

    op.create_table(
        "evaluation_scored_factors",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "extraction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
            nullable=False,
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
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("weight", sa.Numeric(6, 3), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_citation", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_evaluation_scored_tenant_opp_sort",
        "evaluation_scored_factors",
        ["tenant_id", "opportunity_id", "sort_order"],
    )

    # ── solicitation_extractions: evaluation_count column ──────────
    op.add_column(
        "solicitation_extractions",
        sa.Column(
            "evaluation_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("solicitation_extractions", "evaluation_count")

    op.drop_index(
        "ix_evaluation_scored_tenant_opp_sort", table_name="evaluation_scored_factors"
    )
    op.drop_table("evaluation_scored_factors")
    op.drop_index(
        "ix_evaluation_pass_fail_tenant_opp_sort",
        table_name="evaluation_pass_fail_items",
    )
    op.drop_table("evaluation_pass_fail_items")

    op.drop_index(
        "ix_pursuit_teaming_partners_tenant_pursuit",
        table_name="pursuit_teaming_partners",
    )
    op.drop_table("pursuit_teaming_partners")
    op.drop_index(
        "ix_pursuit_key_personnel_tenant_pursuit",
        table_name="pursuit_key_personnel",
    )
    op.drop_table("pursuit_key_personnel")
    op.drop_index(
        "ix_pursuit_past_performance_tenant_pursuit",
        table_name="pursuit_past_performance",
    )
    op.drop_table("pursuit_past_performance")

    op.drop_column("pursuits", "discriminators")
    op.drop_column("pursuits", "win_themes")
