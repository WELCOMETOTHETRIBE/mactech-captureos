"""Tenant-scoped cache of plain-English explanations for jargon terms.

Phase 3 Week 10 (UX overhaul Sprint 2). The "Explain this" right rail
on the opportunity detail page renders Claude-generated explanations
on click; results are cached here so subsequent clicks for the same
term + same prompt version don't spend tokens.

Caching strategy:
  - keyed by (slug, prompt_version) globally (not per-tenant) for now —
    explanations of "NAICS 541512" or "SDVOSB" don't vary by tenant.
  - tenant_id is recorded on first generation purely for audit, not
    used in lookup.
  - prompt_version bump invalidates the cache without a deletion sweep.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class TermExplanation(Base):
    __tablename__ = "term_explanations"
    __table_args__ = (
        UniqueConstraint("slug", "prompt_version", name="uq_term_explanations_slug_version"),
        Index("ix_term_explanations_slug", "slug"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    # Slug format: <kind>:<value>
    #   "naics:541512", "set_aside:SDVOSB", "notice_type:sources_sought",
    #   "score_component:naics_match"
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)

    first_requested_by_tenant_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
