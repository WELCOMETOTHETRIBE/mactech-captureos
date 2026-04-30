"""Helper for emitting audit events.

The :func:`record_event` function is the single entry point. Both API
routes (when a user takes action) and worker tasks (when the system
detects something) call it.

Audit emission is best-effort — never block the primary mutation if
audit insertion fails. We log the failure and continue. If you genuinely
need transactional auditing, adopt SAVEPOINT semantics in the caller;
the default is "fire and forget within the active session."
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db.models import AuditEvent

log = logging.getLogger(__name__)


async def record_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    actor_user_id: UUID | None = None,
    actor_founder_id: UUID | None = None,
    actor_label: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent | None:
    """Insert an audit event in the active session.

    Caller is responsible for committing/flushing the session afterward.
    Returns the inserted event for convenience, or None if insertion
    failed (and logs the failure).
    """
    try:
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_founder_id=actor_founder_id,
            actor_label=actor_label,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
        session.add(event)
        return event
    except Exception as exc:  # never break the caller's primary mutation
        log.warning(
            "audit.record_event failed: type=%s entity=%s/%s err=%s",
            event_type,
            entity_type,
            entity_id,
            exc,
        )
        return None
