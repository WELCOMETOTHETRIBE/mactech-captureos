"""Score opportunities for the MacTech tenant + generate why_it_matters.

Per docs/SCHEMA.md §scoring + docs/MACTECH_PLAYBOOK.md §1. The task:

  1. Build a per-tenant ScoringContext from saved_searches + tenant config.
  2. Pull a batch of opportunities that need scoring (no row in
     opportunity_scores yet, or scored_at older than threshold).
  3. For each opp:
       a. Pull enrichment row (incumbent UEI, end_date, exclusion status).
       b. Compute the 7-component weighted sum.
       c. If score >= threshold and we have an Anthropic key, generate the
          why_it_matters paragraph via Claude Haiku.
       d. Upsert into opportunity_scores.

  4. Fan-out: a parallel beat task computes capability-similarity boosts via
     pgvector once embeddings populate (returns 0..5 added to the score).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import (
    Founder,
    NaicsCode,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    SavedSearch,
    Tenant,
)
from mactech_intelligence import (
    AnthropicLLMClient,
    OpportunityFacts,
    ScoringContext,
    generate_why_it_matters,
    score_opportunity,
)
from mactech_intelligence.why_it_matters import WhyItMattersInput
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 25
WHY_IT_MATTERS_MIN_SCORE = 60  # only spend tokens on plausible candidates


@dataclass
class ScoreStats:
    tenant_slug: str
    scored: int
    why_it_matters_generated: int
    skipped_no_naics: int
    duration_ms: int


async def _build_context(session: AsyncSession, tenant: Tenant) -> ScoringContext:
    # NAICS tiers — per-tenant override first, fall back to global seed.
    # When tenant.target_naics is set, the user picked exactly the codes
    # they care about during onboarding. Treat them all as PRIMARY tier
    # (full 25 pts). Secondary set is empty in that case — the user's
    # explicit list IS the universe of what they're pursuing.
    # When tenant.target_naics is null, use the seeded MacTech tiering
    # from naics_codes.mactech_tier (existing Phase 1 behaviour).
    target = list(tenant.target_naics or [])
    if target:
        primary_rows: list[str] = target
        secondary_rows: list[str] = []
    else:
        primary_rows = (
            await session.execute(
                select(NaicsCode.code).where(NaicsCode.mactech_tier == "primary")
            )
        ).scalars().all()
        secondary_rows = (
            await session.execute(
                select(NaicsCode.code).where(NaicsCode.mactech_tier == "secondary")
            )
        ).scalars().all()

    # Keywords + sweet-spot from saved_searches.filters
    searches = (
        await session.execute(
            select(SavedSearch).where(SavedSearch.tenant_id == tenant.id)
        )
    ).scalars().all()
    keywords: list[str] = []
    seen: set[str] = set()
    for s in searches:
        for k in (s.filters or {}).get("keywords", []) or []:
            kl = k.strip().lower()
            if kl and kl not in seen:
                seen.add(kl)
                keywords.append(k.strip())

    # NAICS → founder slug routing via founder_naics_matrix.
    routing_rows = (
        await session.execute(
            text(
                """
                select fnm.naics_code, f.slug
                from founder_naics_matrix fnm
                join founders f on f.id = fnm.founder_id
                """
            )
        )
    ).all()
    naics_to_founder: dict[str, str] = {}
    for code, slug in routing_rows:
        # First-seen wins. matches data file ordering and is good enough
        # for phase 1; the playbook §2 keyword-driven splits arrive in
        # phase 2.
        naics_to_founder.setdefault(code, slug)

    return ScoringContext(
        primary_naics=set(primary_rows),
        secondary_naics=set(secondary_rows),
        keywords=keywords,
        set_aside_sdvosb={"SDVOSBC", "SDVOSBS", "VSA", "VSS"},
        set_aside_small_biz={"SBA", "SBP", "SB"},
        sweet_spot_min=100_000,
        sweet_spot_max=10_000_000,
        naics_to_founder_slug=naics_to_founder,
    )


def _make_facts(
    opp: OpportunityRaw, enr: OpportunityEnriched | None
) -> OpportunityFacts:
    incumbent_excluded: bool | None = None
    incumbent_end = None
    if enr is not None:
        incumbent_end = enr.incumbent_end_date
    return OpportunityFacts(
        naics_code=opp.naics_code,
        set_aside=opp.set_aside,
        posted_at=opp.posted_at,
        title=opp.title,
        description_text=opp.description_text,
        estimated_value_low=opp.estimated_value_low,
        estimated_value_high=opp.estimated_value_high,
        incumbent_uei=enr.incumbent_uei if enr else None,
        incumbent_end_date=incumbent_end,
        incumbent_excluded=incumbent_excluded,
        has_capability_match=False,
        has_capability_match_score=0,
    )


async def _capability_similarity_score(
    session: AsyncSession, tenant_id: UUID, opportunity_id: UUID
) -> tuple[int, list[str]]:
    """Return (0..5 points, list of top capability titles) for the opp.

    Uses pgvector cosine similarity (1 - opp.embedding <=> cap.embedding) and
    scales the max similarity into 5 points. Returns (0, []) when either side
    has no embedding yet.
    """
    rows = (
        await session.execute(
            text(
                """
                select c.title, 1 - (o.embedding <=> c.embedding) as similarity
                from opportunities_raw o, capability_statements c
                where o.id = :opp_id
                  and c.tenant_id = :tenant_id
                  and o.embedding is not null
                  and c.embedding is not null
                order by similarity desc
                limit 3
                """
            ),
            {"opp_id": str(opportunity_id), "tenant_id": str(tenant_id)},
        )
    ).all()
    if not rows:
        return 0, []
    top_sim = float(rows[0][1])
    # Cosine similarity ranges roughly 0..1 for our text. Map 0.55 -> 5,
    # 0.40 -> 0 with linear interpolation in between.
    points = max(0, min(5, int(round(((top_sim - 0.40) / 0.15) * 5))))
    return points, [r[0] for r in rows]


async def score_unscored_batch(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    generate_rationale: bool = True,
    tenant_slug: str | None = None,
) -> ScoreStats:
    """Score the next `batch_size` unscored opportunities for a tenant.

    `tenant_slug` defaults to the legacy `MACTECH_TENANT_SLUG` env var
    so the existing cron beat keeps working unchanged. Net-new tenants
    invoke this with their explicit slug from the onboarding-completion
    Celery task (sprint 15) to bootstrap their initial feed.
    """
    started = datetime.now(UTC)
    if tenant_slug is None:
        tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    session_factory = async_session_factory()
    scored = 0
    rationales = 0
    skipped_no_naics = 0

    async with session_factory() as session:
        async with session.begin():
            tenant = (
                await session.execute(
                    select(Tenant).where(Tenant.slug == tenant_slug)
                )
            ).scalar_one()
            ctx = await _build_context(session, tenant)
            founders_by_slug = {
                f.slug: f
                for f in (
                    await session.execute(
                        select(Founder).where(Founder.tenant_id == tenant.id)
                    )
                ).scalars().all()
            }

            # Find unscored opps (no row in opportunity_scores).
            opps = (
                await session.execute(
                    select(OpportunityRaw)
                    .outerjoin(
                        OpportunityScore,
                        (OpportunityScore.opportunity_id == OpportunityRaw.id)
                        & (OpportunityScore.tenant_id == tenant.id),
                    )
                    .where(OpportunityScore.id.is_(None))
                    .where(OpportunityRaw.naics_code.is_not(None))
                    .order_by(OpportunityRaw.posted_at.desc().nulls_last())
                    .limit(batch_size)
                )
            ).scalars().all()

            llm: AnthropicLLMClient | None = None
            if generate_rationale and anthropic_key:
                llm = AnthropicLLMClient(api_key=anthropic_key)

            for opp in opps:
                if not opp.naics_code:
                    skipped_no_naics += 1
                    continue
                enr = (
                    await session.execute(
                        select(OpportunityEnriched).where(
                            OpportunityEnriched.opportunity_id == opp.id
                        )
                    )
                ).scalar_one_or_none()

                facts = _make_facts(opp, enr)
                cap_pts, cap_titles = await _capability_similarity_score(
                    session, tenant.id, opp.id
                )
                facts = OpportunityFacts(
                    **{**asdict(facts), "has_capability_match_score": cap_pts}
                )
                result = score_opportunity(facts, ctx)

                why_it_matters: str | None = None
                why_model: str | None = None
                if llm is not None and result.score >= WHY_IT_MATTERS_MIN_SCORE:
                    founder = founders_by_slug.get(result.assigned_founder_slug or "")
                    incumbent_amt = (
                        float(enr.incumbent_award_amount)
                        if enr and enr.incumbent_award_amount is not None
                        else None
                    )
                    inp = WhyItMattersInput(
                        title=opp.title,
                        agency=opp.agency,
                        naics_code=opp.naics_code,
                        set_aside=opp.set_aside,
                        notice_type=opp.notice_type,
                        posted_at=opp.posted_at,
                        response_deadline=opp.response_deadline,
                        description=opp.description_text,
                        incumbent_name=enr.incumbent_name if enr else None,
                        incumbent_amount=incumbent_amt,
                        incumbent_excluded=facts.incumbent_excluded,
                        incumbent_end_date=enr.incumbent_end_date if enr else None,
                        capability_titles=cap_titles,
                        founder_slug=result.assigned_founder_slug,
                        founder_pillar=founder.pillar if founder else None,
                    )
                    try:
                        resp = await generate_why_it_matters(llm, inp)
                        why_it_matters = resp.text
                        why_model = resp.model
                        rationales += 1
                    except Exception as exc:  # don't let a single LLM failure tank the batch
                        log.warning("why_it_matters failed for %s: %s", opp.id, exc)

                assigned_id = (
                    founders_by_slug[result.assigned_founder_slug].id
                    if result.assigned_founder_slug
                    and result.assigned_founder_slug in founders_by_slug
                    else None
                )
                stmt = (
                    pg_insert(OpportunityScore)
                    .values(
                        tenant_id=tenant.id,
                        opportunity_id=opp.id,
                        score=result.score,
                        score_breakdown=result.breakdown,
                        assigned_founder_id=assigned_id,
                        why_it_matters=why_it_matters,
                        why_it_matters_model=why_model,
                        scored_at=datetime.now(UTC),
                    )
                    .on_conflict_do_update(
                        index_elements=["tenant_id", "opportunity_id"],
                        set_={
                            "score": result.score,
                            "score_breakdown": result.breakdown,
                            "assigned_founder_id": assigned_id,
                            "why_it_matters": why_it_matters,
                            "why_it_matters_model": why_model,
                            "scored_at": datetime.now(UTC),
                        },
                    )
                )
                await session.execute(stmt)
                scored += 1

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return ScoreStats(
        tenant_slug=tenant_slug,
        scored=scored,
        why_it_matters_generated=rationales,
        skipped_no_naics=skipped_no_naics,
        duration_ms=duration_ms,
    )


async def score_one_opportunity(opportunity_id: UUID | str) -> dict[str, Any]:
    """Convenience for ad-hoc enqueue. Always regenerates why_it_matters when
    above the threshold."""
    opp_uuid = UUID(str(opportunity_id))
    tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    session_factory = async_session_factory()

    async with session_factory() as session:
        async with session.begin():
            tenant = (
                await session.execute(
                    select(Tenant).where(Tenant.slug == tenant_slug)
                )
            ).scalar_one()
            ctx = await _build_context(session, tenant)
            founders_by_slug = {
                f.slug: f
                for f in (
                    await session.execute(
                        select(Founder).where(Founder.tenant_id == tenant.id)
                    )
                ).scalars().all()
            }
            opp = (
                await session.execute(
                    select(OpportunityRaw).where(OpportunityRaw.id == opp_uuid)
                )
            ).scalar_one()
            enr = (
                await session.execute(
                    select(OpportunityEnriched).where(
                        OpportunityEnriched.opportunity_id == opp_uuid
                    )
                )
            ).scalar_one_or_none()
            facts = _make_facts(opp, enr)
            cap_pts, cap_titles = await _capability_similarity_score(
                session, tenant.id, opp.id
            )
            facts = OpportunityFacts(
                **{**asdict(facts), "has_capability_match_score": cap_pts}
            )
            result = score_opportunity(facts, ctx)

            why_text: str | None = None
            why_model: str | None = None
            if anthropic_key and result.score >= WHY_IT_MATTERS_MIN_SCORE:
                founder = founders_by_slug.get(result.assigned_founder_slug or "")
                incumbent_amt = (
                    float(enr.incumbent_award_amount)
                    if enr and enr.incumbent_award_amount is not None
                    else None
                )
                client = AnthropicLLMClient(api_key=anthropic_key)
                inp = WhyItMattersInput(
                    title=opp.title,
                    agency=opp.agency,
                    naics_code=opp.naics_code,
                    set_aside=opp.set_aside,
                    notice_type=opp.notice_type,
                    posted_at=opp.posted_at,
                    response_deadline=opp.response_deadline,
                    description=opp.description_text,
                    incumbent_name=enr.incumbent_name if enr else None,
                    incumbent_amount=incumbent_amt,
                    incumbent_excluded=facts.incumbent_excluded,
                    incumbent_end_date=enr.incumbent_end_date if enr else None,
                    capability_titles=cap_titles,
                    founder_slug=result.assigned_founder_slug,
                    founder_pillar=founder.pillar if founder else None,
                )
                resp = await generate_why_it_matters(client, inp)
                why_text = resp.text
                why_model = resp.model

            assigned_id = (
                founders_by_slug[result.assigned_founder_slug].id
                if result.assigned_founder_slug
                and result.assigned_founder_slug in founders_by_slug
                else None
            )
            stmt = (
                pg_insert(OpportunityScore)
                .values(
                    tenant_id=tenant.id,
                    opportunity_id=opp.id,
                    score=result.score,
                    score_breakdown=result.breakdown,
                    assigned_founder_id=assigned_id,
                    why_it_matters=why_text,
                    why_it_matters_model=why_model,
                    scored_at=datetime.now(UTC),
                )
                .on_conflict_do_update(
                    index_elements=["tenant_id", "opportunity_id"],
                    set_={
                        "score": result.score,
                        "score_breakdown": result.breakdown,
                        "assigned_founder_id": assigned_id,
                        "why_it_matters": why_text,
                        "why_it_matters_model": why_model,
                        "scored_at": datetime.now(UTC),
                    },
                )
            )
            await session.execute(stmt)

    return {
        "opportunity_id": str(opp_uuid),
        "score": result.score,
        "breakdown": result.breakdown,
        "assigned_founder_slug": result.assigned_founder_slug,
        "why_it_matters": why_text,
        "why_it_matters_model": why_model,
        "capability_match_titles": cap_titles,
    }


@celery_app.task(name="mactech.score.batch")
def score_batch_task(batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    return asdict(asyncio.run(score_unscored_batch(batch_size=batch_size)))


@celery_app.task(name="mactech.score.one")
def score_one_task(opportunity_id: str) -> dict[str, Any]:
    return asyncio.run(score_one_opportunity(opportunity_id))


async def first_feed_score_for_tenant(
    tenant_slug: str, *, batch_size: int = 200
) -> dict[str, Any]:
    """Run an immediate scoring sweep for a freshly-onboarded tenant.

    Larger batch_size than the cron beat (which runs every 20 min on
    batch=64) so a brand-new tenant sees their first slate of scored
    opportunities within the first run instead of three.
    """
    stats = await score_unscored_batch(
        batch_size=batch_size,
        generate_rationale=True,
        tenant_slug=tenant_slug,
    )
    return asdict(stats)


@celery_app.task(name="mactech.onboarding.first_score")
def first_score_task(tenant_slug: str, batch_size: int = 200) -> dict[str, Any]:
    """Celery task fired from the API on onboarding completion."""
    return asyncio.run(
        first_feed_score_for_tenant(tenant_slug, batch_size=batch_size)
    )
