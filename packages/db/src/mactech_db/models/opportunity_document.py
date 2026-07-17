"""Per-document acquisition + provenance (Slice 2).

These tables are SHARED (notice-level, no ``tenant_id``), mirroring
``opportunities_enriched`` / ``awards_history`` — the procurement package is a
property of the notice, not of a tenant, so it is fetched and parsed once.

``opportunity_documents`` is one row per distinct binary (keyed by content
hash, so re-fetching an unchanged file is a no-op and a changed file is a new
row that supersedes the old). ``document_sections`` carries the page/section
provenance that the detector cites as evidence.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base

# Explicit processing lifecycle (brief §4). Persisted as String(24).
DOCUMENT_STATUSES = (
    "not_discovered",
    "queued",
    "downloaded",
    "parsed",
    "partially_parsed",
    "access_restricted",
    "unsupported",
    "failed_retryable",
    "failed_permanent",
)

# What the current analysis is based on (brief §4). Stored on
# opportunities_raw.documents_status.completeness.
PACKAGE_COMPLETENESS = (
    "metadata_only",
    "description_only",
    "partial_attachments",
    "all_accessible",
)


class OpportunityDocument(Base):
    __tablename__ = "opportunity_documents"
    __table_args__ = (
        UniqueConstraint(
            "opportunity_id", "content_hash", name="uq_opportunity_documents_opp_hash"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    doc_class: Mapped[str] = mapped_column(
        String(48), nullable=False, server_default=text("'other'")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    doc_format: Mapped[str | None] = mapped_column(String(16), nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_char_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    # Parent archive key when this file came out of a ZIP; null otherwise.
    archived_from: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'not_discovered'")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reprocessed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DocumentSection(Base):
    __tablename__ = "document_sections"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    document_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunity_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized for opportunity-scoped evidence queries without a join.
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    char_end: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
