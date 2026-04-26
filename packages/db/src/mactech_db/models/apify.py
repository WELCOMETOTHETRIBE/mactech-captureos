"""Apify run audit + agency events.

Sprint 19. apify_runs is append-only — every webhook we accept gets a
row, keyed by (run_id, event_type) so resends are deduped. agency_events
is the first concrete output of the Apify pipeline (industry-day
calendar via apify/website-content-crawler).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class ApifyRun(Base):
    __tablename__ = "apify_runs"
    __table_args__ = (
        UniqueConstraint(
            "apify_run_id", "event_type", name="uq_apify_runs_run_event"
        ),
        Index(
            "ix_apify_runs_capability_received",
            "capability",
            "received_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    apify_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    apify_actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capability: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    apify_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    dataset_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    items_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )


class AgencyEvent(Base):
    __tablename__ = "agency_events"
    __table_args__ = (
        UniqueConstraint(
            "source_url", "title", name="uq_agency_events_url_title"
        ),
        Index("ix_agency_events_starts_at", "starts_at"),
        Index("ix_agency_events_agency", "agency"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_host: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str | None] = mapped_column(String(48), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    naics_codes: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    apify_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
