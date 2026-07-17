"""Amendment detection helper for SAM (and any future ingest source).

When an existing opportunity's content hash changes between ingest runs,
that's an amendment. This module:

* Diffs the meaningful fields and produces a structured ``diff_summary``
  the UI can render without re-parsing raw_payload.
* Inserts an :class:`OpportunityAmendment` record.
* Marks all matching :class:`SolicitationExtraction` rows as ``stale``
  so the UI surfaces "this opportunity changed — regenerate the
  matrices."
* Emits one ``opportunity.amendment_detected`` audit event per tenant
  that has a pursuit on the affected opportunity.

The actual re-extraction stays manual — surprise LLM costs during
ingest is a footgun we want to avoid. Users see the stale signal and
trigger regen explicitly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db.audit import record_event
from mactech_db.models import (
    EVENT_OPPORTUNITY_AMENDMENT_DETECTED,
    OpportunityAmendment,
    OpportunityRaw,
    Pursuit,
    SolicitationExtraction,
)

log = logging.getLogger(__name__)


# Fields we surface diffs for. Other raw_payload changes flip the hash
# but aren't worth telling the user about.
DIFFABLE_FIELDS: tuple[str, ...] = (
    "title",
    "response_deadline",
    "posted_at",
    "estimated_value_low",
    "estimated_value_high",
    "naics_code",
    "set_aside",
    "notice_type",
    "description_text",
)


def _value_for_diff(value: Any) -> Any:
    """Make a value JSON-friendly + display-ready."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and len(value) > 500:
        # Description text is the common case; show a tail-end excerpt
        # rather than the full body.
        return value[:500] + "…"
    return value


def _build_diff_summary(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for field in DIFFABLE_FIELDS:
        before = previous.get(field)
        after = current.get(field)
        if before == after:
            continue
        out.append(
            {
                "field": field,
                "before": _value_for_diff(before),
                "after": _value_for_diff(after),
            }
        )
    return out


def snapshot_for_diff(opp: OpportunityRaw) -> dict[str, Any]:
    """Pluck the diffable fields off an OpportunityRaw."""
    return {field: getattr(opp, field, None) for field in DIFFABLE_FIELDS}


async def record_amendment(
    session: AsyncSession,
    *,
    opportunity: OpportunityRaw,
    previous_snapshot: dict[str, Any],
    previous_hash: str | None,
    new_hash: str,
) -> OpportunityAmendment | None:
    """Detect, persist, and announce an amendment.

    Caller has already updated the OpportunityRaw row in the session;
    pass the previous snapshot taken *before* the update plus the prior
    + new hashes. Returns the inserted amendment, or None if the diff
    contained no diffable-field changes (rare but possible — payload
    metadata changed without surfacing).
    """
    current_snapshot = snapshot_for_diff(opportunity)
    diff = _build_diff_summary(previous_snapshot, current_snapshot)
    if not diff:
        log.info(
            "amendment hash changed but no diffable-field changes; "
            "opp=%s previous_hash=%s new_hash=%s",
            opportunity.id,
            previous_hash,
            new_hash,
        )
        return None

    amendment = OpportunityAmendment(
        opportunity_id=opportunity.id,
        previous_hash=previous_hash,
        new_hash=new_hash,
        previous_response_deadline=previous_snapshot.get("response_deadline"),
        new_response_deadline=current_snapshot.get("response_deadline"),
        previous_title=previous_snapshot.get("title"),
        new_title=current_snapshot.get("title"),
        diff_summary=diff,
    )
    session.add(amendment)
    await session.flush()  # need the id for audit payload

    # Mark every tenant's solicitation extraction for this opp as stale.
    await session.execute(
        update(SolicitationExtraction)
        .where(SolicitationExtraction.opportunity_id == opportunity.id)
        .values(status="stale")
    )

    # Emit one audit event per tenant that has a pursuit on this opp.
    pursuits = (
        (await session.execute(select(Pursuit).where(Pursuit.opportunity_id == opportunity.id)))
        .scalars()
        .all()
    )
    seen_tenant_ids: set[UUID] = set()
    for pursuit in pursuits:
        if pursuit.tenant_id in seen_tenant_ids:
            continue
        seen_tenant_ids.add(pursuit.tenant_id)
        await record_event(
            session,
            tenant_id=pursuit.tenant_id,
            event_type=EVENT_OPPORTUNITY_AMENDMENT_DETECTED,
            entity_type="opportunity",
            entity_id=opportunity.id,
            actor_label="worker:sam_ingest",
            payload={
                "amendment_id": str(amendment.id),
                "diff_field_count": len(diff),
                "fields_changed": [d["field"] for d in diff],
                "previous_hash": previous_hash,
                "new_hash": new_hash,
            },
        )

    return amendment
