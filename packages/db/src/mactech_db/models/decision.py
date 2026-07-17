"""Decision-layer persistence (Slice 4).

Tenant-scoped, authoritative decision output that reads the evidence tables
(cyber_scope_analyses, opportunities_enriched, opportunity_documents) and writes
a versioned decision vector + structured gate rows. Two headline fields
(overall_priority, pursuit_lane) are mirrored onto ``opportunity_scores`` for
single-table list/sort views — written in the same transaction to avoid drift.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base

GATE_STATUSES = ("pass", "fail", "unknown", "waived")
GATE_SEVERITIES = ("hard", "soft")


class OpportunityDecisionVector(Base):
    """One authoritative decision per (tenant, opportunity), recomputed on input
    change and versioned for reproducibility."""

    __tablename__ = "opportunity_decision_vectors"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "opportunity_id", name="uq_decision_vectors_tenant_opp"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Nine dimensions (0-100).
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    prime_fit_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    subcontract_fit_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    winability_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deliverability_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    strategic_value_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    urgency_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    evidence_completeness_score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    overall_priority_score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    pursuit_lane: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_codes: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=text("'medium'")
    )
    lane_weight_profile: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'prime'")
    )
    needs_human_review: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )

    # Versioning + reproducibility.
    formula_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    knowledge_pack_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    # Manual override + review.
    manual_lane_override: Mapped[str | None] = mapped_column(String(40), nullable=True)
    override_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OpportunityGate(Base):
    """A deterministic gate result — inspectable, waivable, auditable."""

    __tablename__ = "opportunity_gates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "opportunity_id", "gate_code", name="uq_gates_tenant_opp_code"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    gate_code: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'deterministic'")
    )
    waived_by_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
