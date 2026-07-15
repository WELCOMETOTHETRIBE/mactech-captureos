"""Bid invites forwarded in by email via the Postmark inbound webhook.

Phase 1 flow: a Gmail filter auto-forwards any email whose subject
starts with "Bid Invite:" to the Postmark inbound address; Postmark
POSTs the parsed message to /webhooks/postmark/inbound, which stores
it here keyed by Postmark's MessageID for idempotency. Attachment
*contents* are not stored — only name/type/size metadata — so a
20 MB drawings PDF can't bloat the row.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
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
    postmark_message_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    from_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(String(1024), nullable=False)
    text_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Attachment metadata only: [{"name":..., "content_type":..., "size":...}]
    attachments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'new'")
    )
    # When the original email was sent (Postmark's Date header), best-effort.
    sent_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
