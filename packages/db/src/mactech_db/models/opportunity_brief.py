"""Structured plain-English brief for an opportunity.

Phase 3 Week 11 (UX Sprint 4). Replaces the raw SAM `<pre>` description
on the detail page with a tabbed view: "Plain-English brief" (default)
| "Original SAM text".

Generation is **lazy** — the first time someone opens the detail page
without a brief, the page offers a "Generate brief" button. Clicking
calls Claude Sonnet with the description text and returns structured
JSON which we render as four short sections.

One row per (tenant, opportunity). Regeneration overwrites in place
(unique constraint).
"""

from datetime import datetime
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


class OpportunityBrief(Base):
    __tablename__ = "opportunity_briefs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "opportunity_id", name="uq_opp_briefs_tenant_opp"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Structured fields produced by the LLM.
    scope_one_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    must_have_requirements: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    nice_to_have: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    red_flags_for_small_biz: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    suggested_team_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)

    # Provenance + cost tracking.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
