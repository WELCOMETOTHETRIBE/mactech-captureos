"""Opportunity amendment record.

Closes G2 — when SAM ingest detects that an existing opportunity's
content hash has changed, it creates one of these. The diff_summary
JSONB carries a list of {field, before, after} entries so the UI can
show a meaningful "what changed" view without re-diffing the
raw_payload.

Not tenant-scoped — amendments are facts about the opportunity itself.
Tenants observe amendments via the join from pursuits and via per-tenant
audit events emitted in the same transaction.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class OpportunityAmendment(Base):
    __tablename__ = "opportunity_amendments"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )

    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_response_deadline: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    new_response_deadline: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    previous_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_summary: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)

    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
