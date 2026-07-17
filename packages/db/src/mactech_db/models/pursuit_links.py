"""Junction tables linking a pursuit to selected library records.

Each table answers a different "which X did the capture lead pick for
this specific pursuit?" question. The library tables (past_performance,
founders, teaming_partners) remain the catalog of *available* records;
these junctions record per-pursuit *selection*.

ProposalOS reads these links via the Capture Package handoff to know
which past performance to cite, which key personnel to write resumes
for, and which partners to bring under teaming agreements.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class PursuitPastPerformance(Base):
    __tablename__ = "pursuit_past_performance"
    __table_args__ = (
        UniqueConstraint(
            "pursuit_id",
            "past_performance_id",
            name="uq_pursuit_past_performance_pursuit_pp",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pursuit_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pursuits.id", ondelete="CASCADE"),
        nullable=False,
    )
    past_performance_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("past_performance.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class PursuitKeyPersonnel(Base):
    """Founder selected as a key person for a pursuit.

    V1 treats founders as the universal key-personnel pool. When external
    customers join CaptureOS and need cleared subject-matter experts who
    aren't founders, this table will accept either a founder_id or a
    different person identifier — wait for that need before generalizing.
    """

    __tablename__ = "pursuit_key_personnel"
    __table_args__ = (
        UniqueConstraint(
            "pursuit_id", "founder_id", name="uq_pursuit_key_personnel_pursuit_founder"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pursuit_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pursuits.id", ondelete="CASCADE"),
        nullable=False,
    )
    founder_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("founders.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class PursuitTeamingPartner(Base):
    __tablename__ = "pursuit_teaming_partners"
    __table_args__ = (
        UniqueConstraint(
            "pursuit_id",
            "teaming_partner_id",
            name="uq_pursuit_teaming_partners_pursuit_partner",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    pursuit_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pursuits.id", ondelete="CASCADE"),
        nullable=False,
    )
    teaming_partner_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("teaming_partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
