"""Async PDF import job — OCR + LLM extraction off the request path.

Sprint 18. The API endpoint persists one of these with the PDF blob,
fires the Celery task, and returns the job id. The worker walks the
queue, runs OCR + extraction, creates the past_performance or
capability_statement row, and flips status to done.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base

LIBRARY_IMPORT_KINDS = ("past_performance", "capability_statement")
LIBRARY_IMPORT_STATUSES = ("queued", "running", "done", "failed")


class LibraryImportJob(Base):
    __tablename__ = "library_import_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind in ('past_performance','capability_statement')",
            name="ck_library_import_jobs_kind",
        ),
        CheckConstraint(
            "status in ('queued','running','done','failed')",
            name="ck_library_import_jobs_status",
        ),
        Index("ix_library_import_jobs_tenant_status", "tenant_id", "status"),
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

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")

    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    text_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    notes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
