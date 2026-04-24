"""Voyage embedding worker.

Embeds opportunities_raw and capability_statements in batches. The
embedding column is `vector(1024)` and not declared on the ORM, so we
write it via raw SQL using pgvector's text-list literal format
(string of '[v1,v2,...,v1024]').

Phase 1 Week 4 cadence: every 15 minutes the worker scans for unembedded
rows in either table and processes a batch of up to 64. At ~500 tokens
per opp × 64 batch ≈ 32k tokens/run, well within Voyage's tier limits.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_integrations.voyage import VoyageClient
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 64


@dataclass
class EmbedStats:
    opportunities_embedded: int
    capabilities_embedded: int
    tokens_used: int
    model: str | None


def _embedding_literal(vec: list[float]) -> str:
    """pgvector accepts '[v1,v2,...]' as a text literal cast to vector."""
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


async def _claim_unembedded_opportunities(
    session: AsyncSession, batch_size: int
) -> list[tuple[str, str]]:
    rows = (
        await session.execute(
            text(
                """
                select id::text, coalesce(title, '') || E'\\n\\n' || coalesce(description_text, '')
                from opportunities_raw
                where embedding is null
                  and title is not null
                order by posted_at desc nulls last
                limit :n
                """
            ),
            {"n": batch_size},
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


async def _claim_unembedded_capabilities(
    session: AsyncSession, batch_size: int
) -> list[tuple[str, str]]:
    rows = (
        await session.execute(
            text(
                """
                select id::text, title || E'\\n\\n' || summary
                from capability_statements
                where embedding is null
                limit :n
                """
            ),
            {"n": batch_size},
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


async def _write_embeddings(
    session: AsyncSession, table: str, items: list[tuple[str, list[float]]]
) -> None:
    if not items:
        return
    # Per-row UPDATEs. Tried a single UPDATE ... FROM (VALUES ...) but
    # SQLAlchemy's `:bindparam` prefix collides with Postgres's `::cast`
    # operator inside the VALUES list ("syntax error at or near ':'").
    # Per-row is fine at our batch size (≤128 × ~5 ms = sub-second).
    sql = text(
        f"update {table} set embedding = CAST(:emb AS vector) "
        f"where id = CAST(:id AS uuid)"
    )
    for row_id, emb in items:
        await session.execute(sql, {"id": row_id, "emb": _embedding_literal(emb)})


async def embed_unembedded_batch(*, batch_size: int = DEFAULT_BATCH_SIZE) -> EmbedStats:
    api_key = os.environ.get("VOYAGE_API_KEY", "")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY not set")

    session_factory = async_session_factory()
    opps_count = 0
    caps_count = 0
    tokens = 0
    model: str | None = None

    async with VoyageClient(api_key=api_key) as voyage, session_factory() as session:
        async with session.begin():
            opp_items = await _claim_unembedded_opportunities(session, batch_size)
            cap_items = await _claim_unembedded_capabilities(session, batch_size)

            if opp_items:
                opp_resp = await voyage.embed([t for _, t in opp_items])
                tokens += opp_resp.total_tokens
                model = opp_resp.model
                await _write_embeddings(
                    session,
                    "opportunities_raw",
                    list(zip([i for i, _ in opp_items], opp_resp.embeddings, strict=True)),
                )
                opps_count = len(opp_items)

            if cap_items:
                cap_resp = await voyage.embed([t for _, t in cap_items])
                tokens += cap_resp.total_tokens
                model = cap_resp.model
                await _write_embeddings(
                    session,
                    "capability_statements",
                    list(zip([i for i, _ in cap_items], cap_resp.embeddings, strict=True)),
                )
                caps_count = len(cap_items)

    log.info(
        "embed batch: opps=%d caps=%d tokens=%d model=%s",
        opps_count,
        caps_count,
        tokens,
        model,
    )
    return EmbedStats(
        opportunities_embedded=opps_count,
        capabilities_embedded=caps_count,
        tokens_used=tokens,
        model=model,
    )


@celery_app.task(name="mactech.embed.batch")
def embed_unembedded_batch_task(batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    return asdict(asyncio.run(embed_unembedded_batch(batch_size=batch_size)))
