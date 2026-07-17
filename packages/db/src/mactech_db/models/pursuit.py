from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
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

PURSUIT_STAGES = ("lead", "qualify", "pursue", "propose", "submit", "won", "lost")

# Bid decision is independent of stage — a pursuit can be in "pursue" and
# still have decision="pending" if the team hasn't formally committed yet.
# stage="lost" with decision="no_bid" is the formal kill; stage="lost"
# with decision="bid" means we bid and lost on evaluation.
BID_DECISIONS = ("pending", "bid", "no_bid")


class Pursuit(Base):
    __tablename__ = "pursuits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "opportunity_id", name="uq_pursuits_tenant_opp"),
        CheckConstraint(
            "stage in ('lead','qualify','pursue','propose','submit','won','lost')",
            name="ck_pursuits_stage",
        ),
        CheckConstraint(
            "bid_decision in ('pending','bid','no_bid')",
            name="ck_pursuits_bid_decision",
        ),
        Index("ix_pursuits_tenant_stage", "tenant_id", "stage"),
        Index("ix_pursuits_owner", "owner_founder_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("founders.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False, default="lead")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # High-level capture strategy curated by the capture lead. ProposalOS
    # imports these via the Capture Package and uses them as the spine
    # of per-volume win-theme ghost copy.
    win_themes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    discriminators: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    # Structured bid memo. Stage flow can carry the same information
    # informally ("won" implies a bid was placed) but the structured
    # decision + decider + rationale is what the Capture Package's
    # BidDecisionSection actually wants.
    bid_decision: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    bid_decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    bid_decided_by_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    bid_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_stage_change_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
