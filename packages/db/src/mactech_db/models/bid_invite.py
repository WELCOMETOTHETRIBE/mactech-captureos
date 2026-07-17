"""Bid invites forwarded in by email via the Postmark inbound webhook.

Phase 1 flow: a Gmail filter auto-forwards any email whose subject
starts with "Bid Invite:" to the Postmark inbound address; Postmark
POSTs the parsed message to /webhooks/postmark/inbound, which stores
it here keyed by Postmark's MessageID for idempotency. Attachment
*contents* are not stored — only name/type/size metadata — so a
20 MB drawings PDF can't bloat the row.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base

BID_INVITE_STATUSES = ("new", "reviewed", "archived")


class BidInvite(Base):
    __tablename__ = "bid_invites"
    __table_args__ = (
        CheckConstraint(
            "status in ('new','reviewed','archived')",
            name="ck_bid_invites_status",
        ),
        Index("ix_bid_invites_tenant_status", "tenant_id", "status"),
        Index("ix_bid_invites_tenant_due", "tenant_id", "bid_due_on"),
        Index("ix_bid_invites_tenant_group", "tenant_id", "group_key"),
        # Backs the arrival-order sort; see `arrived_at` below. Created
        # in 0037 via raw DDL because the expression must match the
        # query's coalesce() exactly.
        Index(
            "ix_bid_invites_tenant_arrived",
            "tenant_id",
            func.coalesce(text("sent_at"), text("received_at")).desc(),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Postmark's MessageID — the idempotency key. Postmark retries the
    # webhook on non-200s, so the same message can be POSTed twice.
    postmark_message_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Attachment metadata only: [{"name":..., "content_type":..., "size":...}]
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'new'"))
    # When the original email was sent (Postmark's Date header), best-effort.
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    @hybrid_property
    def arrived_at(self) -> datetime:
        """When the email actually arrived — the only honest sort key.

        `received_at` is ingest time (server_default=now()), so the mbox
        backfill stamped every historical message with its import
        timestamp; their real chronology only survives in `sent_at`.
        Prefer the Date header and fall back to ingest time for the rare
        message with an unparseable or absent one.
        """
        return self.sent_at or self.received_at

    @arrived_at.inplace.expression
    @classmethod
    def _arrived_at_expr(cls):
        return func.coalesce(cls.sent_at, cls.received_at)

    # ── Parsed fields (mactech_intelligence.bid_invite_parser) ──
    # Populated at ingest; nullable because parsing is best-effort and
    # historical rows are backfilled via POST /bid-invites/reparse.
    # kind: invite | reminder | due_date_change | addendum | message |
    #       reply | other
    kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # The trade/scope BuildingConnected invites us to price
    # (title reads "{project}: {bid package}").
    bid_package: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gc_company: Mapped[str | None] = mapped_column(String(320), nullable=True)
    lead_name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    lead_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    lead_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bid_due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # BuildingConnected's stable RFP id (24-hex from /rfps/{id}/bid links;
    # present on reminder/message mail, absent on first-touch invites).
    rfp_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rfp_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Message-mail subheading, e.g. "Due Date Extended", "Addendum #01 …".
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # Normalized project identity (bid_invite_routing.project_group_key):
    # ties an invite + its reminders + due-date changes to one
    # solicitation for linking and the UI's card grouping.
    group_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Set when the invite's project is promoted into the pipeline — the
    # buildingconnected-sourced opportunities_raw row the pursuit hangs
    # off. All emails in a group share the link.
    opportunity_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="SET NULL"),
        nullable=True,
    )
