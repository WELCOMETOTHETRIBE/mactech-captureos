"""Machine-generated pursuit plan (Slice 6).

``pursuit_recommendations`` is the engine's regenerable plan for a notice (one
per tenant+opportunity). ``pursuit_actions`` are its ordered, dated next steps.
Distinct from the human-owned kanban ``pursuits`` — a recommendation can create
or link a ``pursuits`` row when a founder commits to it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Date,
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

PURSUIT_ACTION_STATUSES = ("open", "done", "dismissed")


class PursuitRecommendation(Base):
    __tablename__ = "pursuit_recommendations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "opportunity_id", name="uq_pursuit_recs_tenant_opp"),
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
    pursuit_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("pursuits.id", ondelete="SET NULL"), nullable=True
    )
    pursuit_lane: Mapped[str] = mapped_column(String(40), nullable=False)
    executive_decision: Mapped[str] = mapped_column(Text, nullable=False)
    why_this_is_real: Mapped[str | None] = mapped_column(Text, nullable=True)
    mactech_work_package: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocking_issues: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    prime_target_names: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    recommended_owner_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    response_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'medium'")
    )
    generated_by: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'deterministic'")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PursuitAction(Base):
    __tablename__ = "pursuit_actions"

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
    recommendation_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pursuit_recommendations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    owner_founder_slug: Mapped[str | None] = mapped_column(String(64), nullable=True)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    dependency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'open'"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
