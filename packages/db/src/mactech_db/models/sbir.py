"""SBIR submission package generations + topic feed.

Two tables:

  `sbir_submissions` — one row per Submission Engine run. Tenant-scoped;
  unique (tenant_id, topic_number) enforces the engine's Phase 0
  duplicate-submission guard. Artifact files live on disk under
  `output_dir` (relative to the repo).

  `sbir_topics` — shared (untenanted) feed of DoD SBIR/STTR topics,
  populated directly from DSIP (dodsbirsttr.mil) by the dsip_ingest worker.
  Mirrors the `agency_events` pattern. Unique (source, topic_number).
  Consumed by the /sbir topics page and the submitter's pre-fill flow
  (`/sbir/submit?topic_id=…`).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Index,
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

SBIR_STATUSES = ("queued", "running", "completed", "failed")
SBIR_DEPTHS = ("scaffold", "standard", "complete")


class SBIRSubmission(Base):
    __tablename__ = "sbir_submissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "topic_number", name="uq_sbir_submissions_tenant_topic"),
        Index(
            "ix_sbir_submissions_tenant_created",
            "tenant_id",
            "created_at",
        ),
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
    created_by_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("founders.id", ondelete="SET NULL"),
        nullable=True,
    )

    topic_number: Mapped[str] = mapped_column(String(64), nullable=False)
    topic_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    proposal_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    component: Mapped[str] = mapped_column(String(32), nullable=False)
    depth: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'queued'"))
    output_dir: Mapped[str] = mapped_column(String(512), nullable=False)
    verify_flags: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


SBIR_TOPIC_STATUSES = ("prerelease", "open", "closed", "unknown")


class SBIRTopic(Base):
    """One SBIR/STTR topic ingested directly from DSIP.

    Shared across tenants — same way `opportunities_raw` and
    `agency_events` are shared. The submitter is tenant-scoped and
    references topics by id when the user clicks 'Use this topic'.
    """

    __tablename__ = "sbir_topics"
    __table_args__ = (
        UniqueConstraint("source", "topic_number", name="uq_sbir_topics_source_topic"),
        Index("ix_sbir_topics_status_close", "status", "close_date"),
        Index("ix_sbir_topics_component", "component"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    topic_number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    component: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phase: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'unknown'")
    )
    prerelease_date: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    open_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    close_date: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    technology_areas: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    modernization_priorities: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    itar_export_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phase_i_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phase_i_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    apify_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # DSIP full-detail enrichment. The daily open-topic ingest fills these on
    # every row; metadata-only rows (e.g. the closed-topic backfill) get them
    # lazily when the user clicks 'Use this topic'. Null until then.
    dsip_enriched_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    dsip_tpoc: Mapped[str | None] = mapped_column(String(512), nullable=True)
    dsip_pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    dsip_pdf_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    dsip_apify_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
