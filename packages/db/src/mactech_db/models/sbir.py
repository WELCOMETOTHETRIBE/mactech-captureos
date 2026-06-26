"""SBIR submission package generations.

Tracks every run of the SBIR Submission Engine (page /sbir). One row per
topic; unique (tenant_id, topic_number) is the duplicate-submission guard
the engine's Phase 0 requires. The actual artifact files live on disk
under `output_dir` (relative to the repo); this row carries metadata,
status, and the verify-flag list surfaced from the run.
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
        UniqueConstraint(
            "tenant_id", "topic_number", name="uq_sbir_submissions_tenant_topic"
        ),
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
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'queued'")
    )
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
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
