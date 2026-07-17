from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Date,
    ForeignKey,
    Numeric,
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


class OpportunityEnriched(Base):
    __tablename__ = "opportunities_enriched"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    incumbent_uei: Mapped[str | None] = mapped_column(String, nullable=True)
    incumbent_name: Mapped[str | None] = mapped_column(String, nullable=True)
    incumbent_contract_id: Mapped[str | None] = mapped_column(String, nullable=True)
    incumbent_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    incumbent_award_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    requirements: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    naics_match_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'usaspending'")
    )
    enriched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class AwardHistory(Base):
    __tablename__ = "awards_history"
    __table_args__ = (UniqueConstraint("source", "award_id", name="uq_awards_history_source_id"),)

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    award_id: Mapped[str] = mapped_column(String, nullable=False)
    piid: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient_uei: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String, nullable=True)
    recipient_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    awarding_agency: Mapped[str | None] = mapped_column(String, nullable=True)
    awarding_subagency: Mapped[str | None] = mapped_column(String, nullable=True)
    naics_code: Mapped[str | None] = mapped_column(
        String, ForeignKey("naics_codes.code"), nullable=True
    )
    award_type: Mapped[str | None] = mapped_column(String, nullable=True)
    obligated_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    base_and_all_options_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    period_of_performance_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_of_performance_current_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_of_performance_potential_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class ExclusionsCache(Base):
    __tablename__ = "exclusions_cache"

    uei: Mapped[str] = mapped_column(String, primary_key=True)
    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exclusion_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
