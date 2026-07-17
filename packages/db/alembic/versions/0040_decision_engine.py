"""Decision engine: gates, decision vectors, mirror columns.

Revision ID: 0040_decision_engine
Revises: 0039_opportunity_documents

Slice 4 of the capture-engine overhaul. Adds the authoritative decision layer:
``opportunity_decision_vectors`` (nine dimensions + lane + versioning) and
``opportunity_gates`` (structured, overriding, auditable). Two headline fields
are mirrored onto ``opportunity_scores`` so list/sort views stay single-table.

Both new tables are tenant-scoped (``tenant_id`` FK, ondelete CASCADE) and
queried only via scoped sessions — the tenant filter is the isolation guard
until RLS lands.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0040_decision_engine"
down_revision: str | Sequence[str] | None = "0039_opportunity_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_decision_vectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relevance_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("prime_fit_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("subcontract_fit_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("winability_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("deliverability_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("strategic_value_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("urgency_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("evidence_completeness_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("overall_priority_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("pursuit_lane", sa.String(40), nullable=False),
        sa.Column("reason_codes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.String(8), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("lane_weight_profile", sa.String(16), nullable=False, server_default=sa.text("'prime'")),
        sa.Column("needs_human_review", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("formula_version", sa.String(16), nullable=True),
        sa.Column("knowledge_pack_version", sa.String(128), nullable=True),
        sa.Column("inputs_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("manual_lane_override", sa.String(40), nullable=True),
        sa.Column("override_note", sa.Text, nullable=True),
        sa.Column("computed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "opportunity_id", name="uq_decision_vectors_tenant_opp"),
    )
    op.create_index("ix_decision_vectors_opp", "opportunity_decision_vectors", ["opportunity_id"])
    op.create_index("ix_decision_vectors_lane", "opportunity_decision_vectors", ["tenant_id", "pursuit_lane"])

    op.create_table(
        "opportunity_gates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opportunity_id", UUID(as_uuid=True), sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gate_code", sa.String(48), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("severity", sa.String(8), nullable=False),
        sa.Column("reason_code", sa.String(48), nullable=True),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("evidence", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(24), nullable=False, server_default=sa.text("'deterministic'")),
        sa.Column("waived_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "opportunity_id", "gate_code", name="uq_gates_tenant_opp_code"),
    )
    op.create_index("ix_gates_opp", "opportunity_gates", ["opportunity_id"])

    # Mirror columns for single-table list/sort views.
    op.add_column("opportunity_scores", sa.Column("overall_priority_score", sa.Integer, nullable=True))
    op.add_column("opportunity_scores", sa.Column("pursuit_lane", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunity_scores", "pursuit_lane")
    op.drop_column("opportunity_scores", "overall_priority_score")
    op.drop_index("ix_gates_opp", table_name="opportunity_gates")
    op.drop_table("opportunity_gates")
    op.drop_index("ix_decision_vectors_lane", table_name="opportunity_decision_vectors")
    op.drop_index("ix_decision_vectors_opp", table_name="opportunity_decision_vectors")
    op.drop_table("opportunity_decision_vectors")
