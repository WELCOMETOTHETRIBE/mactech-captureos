"""Past performance + teaming partner records.

Phase 2 Week 8. Both are tenant-scoped catalogues that the Phase 3
proposal/Sources Sought drafter draws from when generating responses.

Past performance is the firm's prior contract history — narrative
summaries cited in capability responses. Teaming partners is the
relationship roster — primes / subs MacTech might team with.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


PAST_PERFORMANCE_ROLES = ("prime", "sub", "joint_venture", "individual")


class PastPerformance(Base):
    __tablename__ = "past_performance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_past_perf_tenant_title"),
        CheckConstraint(
            "role in ('prime','sub','joint_venture','individual')",
            name="ck_past_perf_role",
        ),
        Index("ix_past_perf_tenant", "tenant_id"),
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
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_agency: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_office: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contract_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="prime")
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    naics_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    related_capability_slugs: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    related_founder_slugs: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TeamingPartner(Base):
    __tablename__ = "teaming_partners"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_teaming_tenant_name"),
        Index("ix_teaming_tenant_status", "tenant_id", "status"),
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uei: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cage_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    capabilities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    naics_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    set_aside_certifications: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
