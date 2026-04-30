"""Audit event log.

Closes D7 — every meaningful change to a pursuit (stage flow, bid
decision, owner change, asset selection) and every system event that
matters (amendment ingest, solicitation extraction completed) is logged
here with who / when / why beyond row-level timestamps.

Tenant-scoped — one customer's audit trail never crosses to another.

Event taxonomy is informal but consistent: dotted paths like
``pursuit.stage_changed`` or ``opportunity.amendment_detected``. Add new
types freely; the column is a String, not an enum, to keep the
trail extensible.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


# Stable event-type strings. Not enforced as an enum — string column for
# extensibility — but new emit sites should reuse one of these or add a
# new constant here for discoverability.
EVENT_PURSUIT_CREATED = "pursuit.created"
EVENT_PURSUIT_STAGE_CHANGED = "pursuit.stage_changed"
EVENT_PURSUIT_OWNER_CHANGED = "pursuit.owner_changed"
EVENT_PURSUIT_NOTES_UPDATED = "pursuit.notes_updated"
EVENT_PURSUIT_WIN_STRATEGY_UPDATED = "pursuit.win_strategy_updated"
EVENT_PURSUIT_BID_DECIDED = "pursuit.bid_decided"
EVENT_PURSUIT_DELETED = "pursuit.deleted"
EVENT_PURSUIT_PAST_PERFORMANCE_REPLACED = "pursuit.past_performance_replaced"
EVENT_PURSUIT_KEY_PERSONNEL_REPLACED = "pursuit.key_personnel_replaced"
EVENT_PURSUIT_TEAMING_PARTNERS_REPLACED = "pursuit.teaming_partners_replaced"

EVENT_OPPORTUNITY_AMENDMENT_DETECTED = "opportunity.amendment_detected"
EVENT_SOLICITATION_EXTRACTION_COMPLETED = "solicitation.extraction_completed"
EVENT_SOLICITATION_EXTRACTION_DELETED = "solicitation.extraction_deleted"

# Tenant SAM verification (B1/B2/B3-on-self).
EVENT_TENANT_SAM_VERIFIED = "tenant.sam_verified"
EVENT_TENANT_SAM_REGISTRATION_STATUS_CHANGED = "tenant.sam_registration_status_changed"
EVENT_TENANT_SAM_EXCLUSION_CHANGED = "tenant.sam_exclusion_changed"


class AuditEvent(Base):
    __tablename__ = "audit_events"

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
    actor_user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("founders.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
