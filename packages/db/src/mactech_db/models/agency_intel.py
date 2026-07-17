"""Cached agency-level NAICS spending rollups from USASpending.gov.

Phase 3 Week 12 (UX Sprint 5). Backs the "Agency intel" card on the
opportunity detail page: how much this agency spent on this NAICS in
the last 12 months, # of awards, average award value, top 5 winners.

One row per (agency_name, naics_code, lookback_days). Refreshed on
demand with a 7-day TTL; the API returns the cached row immediately
even when stale, then fires a refresh in the background. (Stale-while-
revalidate is implemented in the route, not the model.)

Agency name is matched verbatim against USASpending's `awarding_agency`
toptier name. Records that don't resolve (typos, sub-agency strings)
get the `lookup_failed` flag set so we don't retry them every page view.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class AgencyNaicsIntel(Base):
    __tablename__ = "agency_naics_intel"
    __table_args__ = (
        UniqueConstraint(
            "agency_name",
            "naics_code",
            "lookback_days",
            name="uq_agency_intel_lookup",
        ),
        Index(
            "ix_agency_intel_refreshed",
            "agency_name",
            "naics_code",
            "refreshed_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    agency_name: Mapped[str] = mapped_column(String(255), nullable=False)
    naics_code: Mapped[str] = mapped_column(String(8), nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)

    # Aggregates over the last `lookback_days` for this (agency, naics).
    award_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_obligated: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    avg_award_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    median_award_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Top recipients by total $: list of {name, uei, total, award_count}.
    top_recipients: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Set-aside breakdown if available: {SDVOSB: {count, total}, ...}.
    set_aside_breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # If the lookup failed (agency name didn't resolve, USASpending error)
    # we record the failure so we don't retry every detail-page view.
    lookup_failed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    refreshed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
