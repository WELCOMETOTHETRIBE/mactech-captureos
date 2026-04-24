from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, BigInteger, ForeignKey, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class OpportunityRaw(Base):
    __tablename__ = "opportunities_raw"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_opportunities_raw_source_id"),)

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    notice_type: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description_url: Mapped[str | None] = mapped_column(String, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    solicitation_number: Mapped[str | None] = mapped_column(String, nullable=True)
    agency: Mapped[str | None] = mapped_column(String, nullable=True)
    subagency: Mapped[str | None] = mapped_column(String, nullable=True)
    office: Mapped[str | None] = mapped_column(String, nullable=True)
    naics_code: Mapped[str | None] = mapped_column(
        String, ForeignKey("naics_codes.code"), nullable=True
    )
    set_aside: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_value_low: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    estimated_value_high: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    response_deadline: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    place_of_performance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    hash: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    # `embedding vector(1024)` is created in the migration but intentionally
    # not declared in the ORM. Phase 1 Week 2 ingestion does not read or write
    # it; Week 3 enrichment will use raw SQL for the pgvector ops.


class IngestionState(Base):
    __tablename__ = "ingestion_state"

    source: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_cursor: Mapped[str | None] = mapped_column(String, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_count_lifetime: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
