"""Prime-target intelligence (Slice 7).

``prime_targets`` is a SHARED discovery cache (no tenant_id) mirroring
``awards_history`` — a company MacTech might team under is a public fact,
discovered once. ``opportunity_prime_targets`` is the tenant-scoped link:
which primes matter for a given notice, with rationale + evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class PrimeTarget(Base):
    __tablename__ = "prime_targets"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_prime_targets_dedupe_key"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # uei when known, else normalized upper-cased name — the stable identity.
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    uei: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cage_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'historical_awardee'")
    )
    agencies: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    naics_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    recent_award_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    total_recent_award_amount: Mapped[float | None] = mapped_column(
        Numeric, nullable=True
    )
    award_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    contact: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'usaspending'")
    )
    # Optional promotion into the curated teaming CRM.
    teaming_partner_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("teaming_partners.id", ondelete="SET NULL"), nullable=True
    )
    refreshed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class OpportunityPrimeTarget(Base):
    __tablename__ = "opportunity_prime_targets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "opportunity_id", "prime_target_id",
            name="uq_opp_prime_targets_link",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    prime_target_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("prime_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    why_target: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_contact_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    relationship_status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default=text("'none'")
    )
    outreach_deadline: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    confidence: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'possible'")
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
