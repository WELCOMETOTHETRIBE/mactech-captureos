"""Generated proposal draft records.

Phase 3 Week 9. The Sources Sought drafter is the first concrete user
of this table — it stores the LLM-produced response, the prompt context
hash so we can dedupe regenerations, and lets the user edit / version
the draft.

One opportunity can have many drafts (re-generation cycles, different
draft types). A `parent_draft_id` link captures regeneration ancestry
so the UI can show "v2 of v1" lineage.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


DRAFT_TYPES = ("sources_sought", "rfp_response", "compliance_matrix", "white_paper")
DRAFT_STATUSES = ("draft", "reviewed", "submitted", "archived")


class ProposalDraft(Base):
    __tablename__ = "proposal_drafts"
    __table_args__ = (
        CheckConstraint(
            "draft_type in ('sources_sought','rfp_response','compliance_matrix','white_paper')",
            name="ck_drafts_type",
        ),
        CheckConstraint(
            "status in ('draft','reviewed','submitted','archived')",
            name="ck_drafts_status",
        ),
        Index("ix_drafts_tenant_opp", "tenant_id", "opportunity_id"),
        Index("ix_drafts_tenant_created", "tenant_id", "created_at"),
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
    parent_draft_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("proposal_drafts.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("founders.id", ondelete="SET NULL"),
        nullable=True,
    )

    draft_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    custom_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_context_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
