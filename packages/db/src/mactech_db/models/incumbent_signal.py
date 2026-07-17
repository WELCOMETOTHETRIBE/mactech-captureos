"""SEC EDGAR distress monitoring per incumbent contractor.

Sprint 22 / strategy doc §3.3. One row per (normalized_name) with
recent SEC filings cadence, last filing date, and a heuristic
distress_score that the recompete UI uses to flag bleeding incumbents.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Date,
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


class IncumbentSignal(Base):
    __tablename__ = "incumbent_signals"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_incumbent_signals_name"),
        Index("ix_incumbent_signals_distress", "distress_score"),
        Index("ix_incumbent_signals_uei", "recipient_uei"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_uei: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cik: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sec_ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sec_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    filings_last_90d_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filings_last_365d_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    most_recent_filing_form: Mapped[str | None] = mapped_column(String(16), nullable=True)
    most_recent_filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    most_recent_8k_items: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    distress_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distress_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    filings: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_refreshed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
