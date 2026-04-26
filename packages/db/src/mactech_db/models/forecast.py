"""Agency procurement forecasts (pre-SAM intent).

Sprint 20. Federal agencies publish forecasts 30-180 days ahead of the
matching SAM.gov solicitation. We scrape via Apify website-content-
crawler + LLM extraction (mactech_workers.tasks.apify_forecasts).
Tenant-shared (forecasts are public-data signal).
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Date,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class ForecastRaw(Base):
    __tablename__ = "forecasts_raw"
    __table_args__ = (
        UniqueConstraint(
            "source_url", "title", name="uq_forecasts_raw_url_title"
        ),
        Index(
            "ix_forecasts_raw_solicitation_date",
            "expected_solicitation_date",
        ),
        Index("ix_forecasts_raw_naics_code", "naics_code"),
        Index("ix_forecasts_raw_agency", "agency"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_run_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contracting_office: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    naics_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    naics_codes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    set_aside: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_value_low: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    estimated_value_high: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True
    )
    estimated_value_text: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    expected_solicitation_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    expected_award_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    period_of_performance_start: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    period_of_performance_end: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    incumbent_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    incumbent_contract_number: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    poc_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    poc_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    forecast_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
