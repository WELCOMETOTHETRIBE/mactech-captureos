"""Score opportunities for the MacTech tenant + generate why_it_matters.

Per docs/SCHEMA.md §scoring + docs/MACTECH_PLAYBOOK.md §1. The task:

  1. Build a per-tenant ScoringContext from saved_searches + tenant config.
  2. Pull a batch of opportunities that need scoring (no row in
     opportunity_scores yet, or scored_at older than threshold).
  3. For each opp:
       a. Pull enrichment row (incumbent UEI, end_date, exclusion status).
       b. Compute the 7-component weighted sum.
       c. Run the parallel high-moat track (UFGS 25 / FRCS cyber) when the
          tenant has high_moat_scoring config; persists alongside the base.
       d. If base score >= 50 and the SAM IVL endpoint hasn't been called
          recently, fetch interested-vendors counts so the high-moat
          velocity component lands populated.
       e. If base score >= threshold and we have an Anthropic key,
          generate the why_it_matters paragraph via Claude Haiku.
       f. Upsert into opportunity_scores.

  4. Fan-out: a parallel beat task computes capability-similarity boosts via
     pgvector once embeddings populate (returns 0..5 added to the score).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml
from mactech_db import async_session_factory
from mactech_db.models import (
    Founder,
    NaicsCode,
    OpportunityBrief,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    SavedSearch,
    Tenant,
)
from mactech_integrations.sam_gov import (
    SamInterestedVendorsClient,
    SamInterestedVendorsError,
)
from mactech_intelligence import (
    AnthropicLLMClient,
    BriefExtractionError,
    ClauseFindings,
    ExtractBriefInput,
    HighMoatConfig,
    HighMoatFacts,
    HighMoatResult,
    OpportunityFacts,
    ScoringContext,
    detect_clauses,
    extract_structured_brief,
    generate_why_it_matters,
    score_high_moat,
    score_opportunity,
)
from mactech_intelligence.extract_brief import PROMPT_VERSION as BRIEF_PROMPT_VERSION
from mactech_intelligence.why_it_matters import WhyItMattersInput
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 25
WHY_IT_MATTERS_MIN_SCORE = 60  # only spend tokens on plausible candidates
BRIEF_MIN_SCORE = 60  # auto-extract a plain-English brief at the same gate;
# the UI promotes brief.scope_one_sentence to the primary list title for
# any opp at this threshold or above (architect plan §7.2 / brief §11 Q2).
HIGH_MOAT_BASE_SCORE_GATE = 50  # only IVL-fetch when general score clears this
IVL_REFETCH_AFTER_DAYS = 7  # don't re-poll the IVL more often than weekly

# Tenant defaults YAML lives at <repo_root>/config/. From this file, we sit
# at apps/workers/src/mactech_workers/tasks/score.py — six parents up is the
# repo root. The env-var override is for dev / test, and matches the pattern
# in apps/api/scripts/seed.py.
_DEFAULT_TENANT_DEFAULTS_PATH = (
    Path(__file__).resolve().parents[5] / "config" / "mactech_tenant_defaults.yml"
)


@lru_cache(maxsize=1)
def _load_high_moat_config_raw() -> dict[str, Any] | None:
    """Read the ``high_moat_scoring`` block from the tenant-defaults YAML.

    Returns ``None`` (and short-circuits the high-moat track) when the
    block is missing, so the legacy scoring behaviour is preserved on
    environments that haven't shipped the new config yet.
    """
    path_str = os.environ.get("MACTECH_TENANT_DEFAULTS_PATH")
    path = Path(path_str) if path_str else _DEFAULT_TENANT_DEFAULTS_PATH
    if not path.exists():
        log.info("high_moat config: %s not found — disabling track", path)
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:
        log.warning("high_moat config: failed to read %s: %s", path, exc)
        return None
    block = data.get("high_moat_scoring")
    if not isinstance(block, dict):
        return None
    return block


def _high_moat_config() -> HighMoatConfig | None:
    raw = _load_high_moat_config_raw()
    if raw is None:
        return None
    return HighMoatConfig(
        weights=dict(raw.get("weights") or {}),
        priority_agencies=list(raw.get("priority_agencies") or []),
        traditional_construction_naics=set(
            raw.get("traditional_construction_naics") or []
        ),
        sweet_spot_min_score=int(raw.get("sweet_spot_min_score") or 80),
    )


def _high_moat_patterns() -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    raw = _load_high_moat_config_raw() or {}
    return (
        {k: list(v) for k, v in (raw.get("clause_patterns") or {}).items()},
        {k: list(v) for k, v in (raw.get("clearance_patterns") or {}).items()},
        {k: list(v) for k, v in (raw.get("role_patterns") or {}).items()},
    )


@dataclass
class ScoreStats:
    tenant_slug: str
    scored: int
    why_it_matters_generated: int
    skipped_no_naics: int
    duration_ms: int
    briefs_generated: int = 0


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
        high_moat_config=_high_moat_config(),
    )


def _tenant_set_aside_certs(tenant: Tenant) -> frozenset[str]:
    """Tenant's set-aside certifications, upper-cased for matching against
    opp.set_aside (also normalised to upper). Maps the YAML
    `set_aside_certifications` column / `sdvosb_status` flag onto the
    SAM.gov set-aside codes the scorer uses."""
    certs: set[str] = set()
    if getattr(tenant, "set_aside_certifications", None):
        for raw in tenant.set_aside_certifications:  # type: ignore[union-attr]
            if isinstance(raw, str):
                certs.add(raw.strip().upper())
    # MacTech tenant tracks SDVOSB via sdvosb_status (Phase 1) instead of a
    # set_aside_certifications array. Mirror that into the matching set so
    # the high-moat set-aside component lands correctly.
    sdvosb = getattr(tenant, "sdvosb_status", None)
    if isinstance(sdvosb, str) and sdvosb.strip().lower() == "certified":
        certs.update({"SDVOSBC", "SDVOSBS", "VSA", "VSS"})
    return frozenset(certs)


async def _maybe_fetch_interested_vendors(
    session: AsyncSession,
    opp: OpportunityRaw,
    *,
    base_score: int,
) -> tuple[int | None, int | None]:
    """Fetch + persist SAM Interested Vendors counts when (a) we already
    have a high-moat-config to score against, (b) the opportunity's base
    score clears the gate, and (c) the IVL hasn't been fetched within
    IVL_REFETCH_AFTER_DAYS.

    Returns (count, cyber_count) — either from the live fetch or from
    the previously-cached columns. Either may be None: count=None means
    'never called'; cyber_count=None tags 'never called' too. The high-moat
    scorer treats either as the inactive tier.
    """
    if _high_moat_config() is None:
        return opp.interested_vendors_count, opp.interested_vendors_cyber_count
    if base_score < HIGH_MOAT_BASE_SCORE_GATE:
        return opp.interested_vendors_count, opp.interested_vendors_cyber_count
    fetched_at = opp.interested_vendors_fetched_at
    if fetched_at is not None and (
        datetime.now(UTC) - fetched_at < timedelta(days=IVL_REFETCH_AFTER_DAYS)
    ):
        return opp.interested_vendors_count, opp.interested_vendors_cyber_count

    sam_key = os.environ.get("SAM_API_KEY") or os.environ.get("SAM_GOV_API_KEY")
    if not sam_key:
        log.info("score: SAM_API_KEY not set — skipping IVL fetch")
        return opp.interested_vendors_count, opp.interested_vendors_cyber_count

    try:
        async with SamInterestedVendorsClient(api_key=sam_key) as client:
            result = await client.list_for_notice(opp.source_id)
    except SamInterestedVendorsError as exc:
        log.warning("score: IVL fetch for %s failed: %s", opp.source_id, exc)
        return opp.interested_vendors_count, opp.interested_vendors_cyber_count

    count = result.count if result.available else None
    cyber = result.cyber_count if result.available else None
    await session.execute(
        update(OpportunityRaw)
        .where(OpportunityRaw.id == opp.id)
        .values(
            interested_vendors_count=count,
            interested_vendors_cyber_count=cyber,
            interested_vendors_fetched_at=datetime.now(UTC),
        )
    )
    return count, cyber


def _build_high_moat_facts(
    *,
    opp: OpportunityRaw,
    findings: ClauseFindings,
    tenant_certs: frozenset[str],
    iv_count: int | None,
    iv_cyber_count: int | None,
) -> HighMoatFacts:
    raw_payload = opp.raw_payload or {}
    is_active = True
    active_field = raw_payload.get("active")
    if isinstance(active_field, str):
        is_active = active_field.strip().lower() not in ("no", "false", "0", "")
    return HighMoatFacts(
        title=opp.title or "",
        naics_code=opp.naics_code,
        set_aside=opp.set_aside,
        agency=opp.agency,
        subagency=opp.subagency,
        is_active=is_active,
        clause_findings=findings,
        interested_vendors_count=iv_count,
        interested_vendors_cyber_count=iv_cyber_count,
        tenant_set_aside_certs=tenant_certs,
        compatible_small_biz=frozenset({"SBA", "SBP", "SB"}),
    )


def _high_moat_flags_payload(
    findings: ClauseFindings, result: HighMoatResult
) -> dict[str, Any]:
    return {
        "clause_hits": list(findings.clause_hits),
        "clearance_hits": list(findings.clearance_hits),
        "role_hits": list(findings.role_hits),
        "top_clearance": findings.top_clearance,
        "is_high_probability_easy_win": result.is_high_probability_easy_win,
        "why_it_matters_seed": result.why_it_matters_seed,
    }


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


async def _maybe_generate_brief(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    opp: OpportunityRaw,
    base_score: int,
    llm: AnthropicLLMClient | None,
) -> bool:
    """Generate a plain-English structured brief when the opportunity
    crosses the auto-brief gate and doesn't already have one.

    Mirrors the discipline of `_maybe_fetch_interested_vendors`: every
    short-circuit returns False so a missing key / missing description /
    pre-existing brief / single LLM failure can't tank the whole
    scoring batch. Returns True only when we actually persisted a new
    brief row.

    Architect plan §7.2 / brief §11 Q2: ~$0.20/day at MacTech scale.
    Cost is bounded by BRIEF_MIN_SCORE (currently 60) and by
    `MAX_DESCRIPTION_CHARS = 12000` inside the extractor.
    """
    if llm is None:
        return False
    if base_score < BRIEF_MIN_SCORE:
        return False
    description = (opp.description_text or "").strip()
    if not description:
        return False

    # Skip if we already have a brief for this (tenant, opp) — the
    # extractor is idempotent but the LLM call isn't free.
    existing_id = (
        await session.execute(
            select(OpportunityBrief.id).where(
                OpportunityBrief.tenant_id == tenant_id,
                OpportunityBrief.opportunity_id == opp.id,
            )
        )
    ).scalar_one_or_none()
    if existing_id is not None:
        return False

    inp = ExtractBriefInput(
        title=opp.title,
        agency=opp.agency,
        notice_type=opp.notice_type,
        set_aside=opp.set_aside,
        naics_code=opp.naics_code,
        posted_at=opp.posted_at,
        response_deadline=opp.response_deadline,
        description=description,
    )
    try:
        result = await extract_structured_brief(llm, inp)
    except BriefExtractionError as exc:
        log.warning("auto-brief: bad JSON for %s: %s", opp.id, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        log.warning("auto-brief: extract failed for %s: %s", opp.id, exc)
        return False

    session.add(
        OpportunityBrief(
            tenant_id=tenant_id,
            opportunity_id=opp.id,
            scope_one_sentence=result.scope_one_sentence,
            must_have_requirements=result.must_have_requirements,
            nice_to_have=result.nice_to_have,
            red_flags_for_small_biz=result.red_flags_for_small_biz,
            suggested_team_roles=result.suggested_team_roles,
            model=result.response.model,
            prompt_version=BRIEF_PROMPT_VERSION,
            input_tokens=result.response.input_tokens,
            output_tokens=result.response.output_tokens,
            description_chars=result.description_chars,
        )
    )
    await session.flush()
    return True


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
    briefs = 0

    async with session_factory() as session, session.begin():
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
                # attachment_text is a deferred column; the high-moat clause
                # scan reads it below. Without undefer() the plain attribute
                # access emits a lazy load outside the async greenlet and
                # raises MissingGreenlet, which the caller swallows as
                # scored=0 — the silent scoring outage from 2026-05-22.
                .options(undefer(OpportunityRaw.attachment_text))
                .outerjoin(
                    OpportunityScore,
                    (OpportunityScore.opportunity_id == OpportunityRaw.id)
                    & (OpportunityScore.tenant_id == tenant.id),
                )
                .where(OpportunityScore.id.is_(None))
                .where(OpportunityRaw.naics_code.is_not(None))
                # Don't spend an LLM rationale scoring a notice that can no
                # longer be bid. Null deadlines are kept (unknown != closed),
                # matching the list view's expiry filter.
                .where(
                    (OpportunityRaw.response_deadline.is_(None))
                    | (OpportunityRaw.response_deadline >= func.now())
                )
                .order_by(OpportunityRaw.posted_at.desc().nulls_last())
                .limit(batch_size)
            )
        ).scalars().all()

        llm: AnthropicLLMClient | None = None
        if generate_rationale and anthropic_key:
            llm = AnthropicLLMClient(api_key=anthropic_key)

        tenant_certs = _tenant_set_aside_certs(tenant)
        hm_cfg = _high_moat_config()
        clause_patterns, clearance_patterns, role_patterns = _high_moat_patterns()

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

            hm_score: int | None = None
            hm_breakdown: dict[str, Any] | None = None
            hm_flags: dict[str, Any] | None = None
            if hm_cfg is not None and clause_patterns:
                iv_count, iv_cyber = await _maybe_fetch_interested_vendors(
                    session, opp, base_score=result.score
                )
                findings = detect_clauses(
                    title=opp.title,
                    description_text=opp.description_text,
                    attachment_text=opp.attachment_text,
                    clause_patterns=clause_patterns,
                    clearance_patterns=clearance_patterns,
                    role_patterns=role_patterns,
                )
                hm_facts = _build_high_moat_facts(
                    opp=opp,
                    findings=findings,
                    tenant_certs=tenant_certs,
                    iv_count=iv_count,
                    iv_cyber_count=iv_cyber,
                )
                hm_result = score_high_moat(hm_facts, hm_cfg)
                hm_score = hm_result.score
                hm_breakdown = hm_result.breakdown
                hm_flags = _high_moat_flags_payload(findings, hm_result)

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
                    high_moat_score=hm_score,
                    high_moat_breakdown=hm_breakdown,
                    high_moat_flags=hm_flags,
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
                        "high_moat_score": hm_score,
                        "high_moat_breakdown": hm_breakdown,
                        "high_moat_flags": hm_flags,
                    },
                )
            )
            await session.execute(stmt)
            scored += 1

            # Auto-brief: when the opp scores >= 60 and we have an
            # Anthropic key, generate the plain-English structured brief
            # so the list page can show a human-readable title rather
            # than the raw SAM text. Helper is idempotent — won't fire
            # on opps that already have a brief.
            if await _maybe_generate_brief(
                session,
                tenant_id=tenant.id,
                opp=opp,
                base_score=result.score,
                llm=llm,
            ):
                briefs += 1

    duration_ms = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return ScoreStats(
        tenant_slug=tenant_slug,
        scored=scored,
        why_it_matters_generated=rationales,
        skipped_no_naics=skipped_no_naics,
        duration_ms=duration_ms,
        briefs_generated=briefs,
    )


async def score_one_opportunity(opportunity_id: UUID | str) -> dict[str, Any]:
    """Convenience for ad-hoc enqueue. Always regenerates why_it_matters when
    above the threshold."""
    opp_uuid = UUID(str(opportunity_id))
    tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    session_factory = async_session_factory()

    async with session_factory() as session, session.begin():
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
                select(OpportunityRaw)
                .options(undefer(OpportunityRaw.attachment_text))
                .where(OpportunityRaw.id == opp_uuid)
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

        tenant_certs = _tenant_set_aside_certs(tenant)
        hm_cfg = _high_moat_config()
        clause_patterns, clearance_patterns, role_patterns = _high_moat_patterns()
        hm_score: int | None = None
        hm_breakdown: dict[str, Any] | None = None
        hm_flags: dict[str, Any] | None = None
        if hm_cfg is not None and clause_patterns:
            iv_count, iv_cyber = await _maybe_fetch_interested_vendors(
                session, opp, base_score=result.score
            )
            findings = detect_clauses(
                title=opp.title,
                description_text=opp.description_text,
                attachment_text=opp.attachment_text,
                clause_patterns=clause_patterns,
                clearance_patterns=clearance_patterns,
                role_patterns=role_patterns,
            )
            hm_facts = _build_high_moat_facts(
                opp=opp,
                findings=findings,
                tenant_certs=tenant_certs,
                iv_count=iv_count,
                iv_cyber_count=iv_cyber,
            )
            hm_result = score_high_moat(hm_facts, hm_cfg)
            hm_score = hm_result.score
            hm_breakdown = hm_result.breakdown
            hm_flags = _high_moat_flags_payload(findings, hm_result)

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
                high_moat_score=hm_score,
                high_moat_breakdown=hm_breakdown,
                high_moat_flags=hm_flags,
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
                    "high_moat_score": hm_score,
                    "high_moat_breakdown": hm_breakdown,
                    "high_moat_flags": hm_flags,
                },
            )
        )
        await session.execute(stmt)

        # Auto-brief on the same gate as the batch path. Construct the
        # LLM client lazily so the ad-hoc call still works when the key
        # is missing.
        brief_generated = False
        if anthropic_key:
            brief_llm = AnthropicLLMClient(api_key=anthropic_key)
            brief_generated = await _maybe_generate_brief(
                session,
                tenant_id=tenant.id,
                opp=opp,
                base_score=result.score,
                llm=brief_llm,
            )

    return {
        "opportunity_id": str(opp_uuid),
        "score": result.score,
        "breakdown": result.breakdown,
        "assigned_founder_slug": result.assigned_founder_slug,
        "why_it_matters": why_text,
        "why_it_matters_model": why_model,
        "capability_match_titles": cap_titles,
        "high_moat_score": hm_score,
        "high_moat_breakdown": hm_breakdown,
        "high_moat_flags": hm_flags,
        "brief_generated": brief_generated,
    }


async def score_unscored_batch_all_tenants(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    generate_rationale: bool = True,
    only_tenant_slug: str | None = None,
) -> list[ScoreStats]:
    """Fan out scoring across every tenant.

    Mirrors `send_digest_to_all_founders` (sprint 12). For each tenant
    (ordered by slug for stable runs), invoke `score_unscored_batch`
    with the tenant pinned. `only_tenant_slug` (or the legacy
    `MACTECH_PIN_TENANT_SLUG` env var) restricts to a single tenant.

    Per-tenant errors don't tank the loop — they're logged and the run
    continues so a misconfigured tenant can't starve everyone else.
    """
    pin = (
        only_tenant_slug
        or os.environ.get("MACTECH_PIN_TENANT_SLUG")
        or None
    )
    session_factory = async_session_factory()
    async with session_factory() as session:
        stmt = select(Tenant)
        if pin:
            stmt = stmt.where(Tenant.slug == pin)
        else:
            stmt = stmt.order_by(Tenant.slug)
        tenant_slugs = [
            t.slug for t in (await session.execute(stmt)).scalars().all()
        ]

    results: list[ScoreStats] = []
    for slug in tenant_slugs:
        try:
            stats = await score_unscored_batch(
                batch_size=batch_size,
                generate_rationale=generate_rationale,
                tenant_slug=slug,
            )
        except Exception as exc:
            log.exception("score fan-out failed for tenant=%s: %s", slug, exc)
            stats = ScoreStats(
                tenant_slug=slug,
                scored=0,
                why_it_matters_generated=0,
                skipped_no_naics=0,
                duration_ms=0,
                briefs_generated=0,
            )
        results.append(stats)
    return results


@celery_app.task(name="mactech.score.batch")
def score_batch_task(batch_size: int = DEFAULT_BATCH_SIZE) -> list[dict[str, Any]]:
    return [
        asdict(s)
        for s in asyncio.run(
            score_unscored_batch_all_tenants(batch_size=batch_size)
        )
    ]


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
