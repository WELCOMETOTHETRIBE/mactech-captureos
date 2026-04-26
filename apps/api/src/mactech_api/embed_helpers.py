"""Inline embedding for capability statements.

Phase 3 Week 15 (UX Sprint 10). Closes the 15-minute lag between
"user creates/updates a capability statement" and "the embedding worker
picks it up." We now fire a Voyage call inline on every POST/PATCH/PDF-
import so the new capability is immediately participating in opportunity
scoring.

Fail-soft: if Voyage is rate-limited or times out, log a warning and
return — the existing embed worker will pick up the row on its next
15-minute tick (because we left `embedding` null on failure).
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_integrations.voyage import VoyageClient

log = logging.getLogger(__name__)

EMBED_TIMEOUT_SECS = 8.0


def _embedding_literal(emb: list[float]) -> str:
    """pgvector accepts a string '[v1,v2,...]'."""
    return "[" + ",".join(f"{v:.6f}" for v in emb) + "]"


async def embed_capability_inline(
    session: AsyncSession,
    capability_id: str,
    *,
    title: str,
    summary: str,
) -> bool:
    """Embed a single capability and write the vector to the row.

    Returns True if the embedding landed; False if we fail-softed (and
    the worker will retry). Never raises.
    """
    api_key = os.environ.get("VOYAGE_API_KEY", "")
    if not api_key:
        log.warning(
            "embed_capability_inline skipped — VOYAGE_API_KEY not set; "
            "the embed worker will pick up capability %s on its next tick",
            capability_id,
        )
        return False

    inp = f"{title.strip()}\n\n{summary.strip()}"
    if not inp.strip():
        log.warning("embed_capability_inline got empty input for %s", capability_id)
        return False

    try:
        async with VoyageClient(api_key=api_key) as voyage:
            resp = await voyage.embed([inp])
    except Exception as exc:
        log.warning(
            "embed_capability_inline failed for %s (%s) — worker will retry",
            capability_id,
            exc,
        )
        return False

    if not resp.embeddings:
        log.warning(
            "embed_capability_inline got empty embedding response for %s",
            capability_id,
        )
        return False

    vec = resp.embeddings[0]
    try:
        await session.execute(
            text(
                "update capability_statements set embedding = CAST(:emb AS vector) "
                "where id = CAST(:id AS uuid)"
            ),
            {"id": capability_id, "emb": _embedding_literal(vec)},
        )
    except Exception as exc:
        log.warning(
            "embed_capability_inline write failed for %s (%s) — worker will retry",
            capability_id,
            exc,
        )
        return False

    log.info(
        "embedded capability %s inline (model=%s tokens=%d)",
        capability_id,
        resp.model,
        resp.total_tokens,
    )
    return True
