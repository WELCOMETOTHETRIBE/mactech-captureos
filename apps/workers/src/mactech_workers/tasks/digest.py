"""Morning digest delivery.

Renders each digest-enabled founder's top-N scored opportunities + the
Claude-written rationale + 1-line incumbent summary, then sends via
Resend. Phase 1 success criterion: 6am ET weekdays, founders receive
the email in their inbox.

Domain-verification status is the gating factor for delivery to anyone
but `patrick@mactechsolutionsllc.com` (Resend's free-tier rule). The
worker will silently fail per-recipient on 403 and continue with the
others; failures are logged but don't tank the batch.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from uuid import UUID
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import (
    Founder,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    SavedSearch,
    Tenant,
)
from mactech_integrations.resend import ResendClient, ResendError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_TOP_N = 5
MIN_SCORE_FOR_DIGEST = 60
SAVED_SEARCH_HITS_CAP = 5  # per search; bound email length


@dataclass
class DigestRow:
    title: str
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    agency_short: str | None
    score: int
    why_it_matters: str | None
    incumbent_summary: str | None
    sam_link: str | None
    # High-moat track. Both None for rows ranked by the general score.
    high_moat_score: int | None = None
    is_sweet_spot: bool = False


@dataclass
class SavedSearchHits:
    search_id: UUID
    search_name: str
    rows: list[DigestRow]


@dataclass
class DigestSendStats:
    founder_slug: str
    founder_name: str
    recipient: str | None
    items_count: int
    saved_search_hit_count: int
    sent: bool
    skipped_reason: str | None
    message_id: str | None


def _short_agency(full_path: str | None) -> str | None:
    if not full_path:
        return None
    return full_path.split(".")[0].strip()


def _incumbent_one_liner(enr: OpportunityEnriched | None) -> str | None:
    if enr is None or not enr.incumbent_name:
        return None
    parts = [enr.incumbent_name]
    if enr.incumbent_award_amount is not None:
        parts.append(
            f"${float(enr.incumbent_award_amount):,.0f} prior obligations"
        )
    return " — ".join(parts)


async def _load_saved_search_hits(
    session: AsyncSession,
    *,
    tenant: Tenant,
    founder: Founder,
) -> list[SavedSearchHits]:
    """Saved-search hits scored above each search's threshold and not yet
    delivered. Caller is responsible for stamping ``last_delivered_at``
    after a successful send.

    V1 keyword/set-aside filtering: applied as ANY-of-list. NAICS
    filtering same. Empty filter list = no filter on that field (any
    value matches).
    """
    searches = (
        await session.execute(
            select(SavedSearch).where(
                SavedSearch.tenant_id == tenant.id,
                SavedSearch.owner_founder_id == founder.id,
                SavedSearch.alert_cadence == "daily",
            )
        )
    ).scalars().all()

    out: list[SavedSearchHits] = []
    for search in searches:
        channels = search.alert_channels or []
        if isinstance(channels, list) and "email" not in channels:
            continue
        filters = search.filters or {}
        naics_codes = list(filters.get("naics") or [])
        set_asides = list(filters.get("set_asides") or [])
        keywords = [k for k in (filters.get("keywords") or []) if k.strip()]
        # Per-search score-column switch. The high-moat saved search
        # ("Patrick — UFGS 25 / FRCS Cyber") sets this to "high_moat_score"
        # so its alert_threshold (80) is checked against the parallel
        # column and the result set is ranked by the OT/ICS rubric, not
        # the general 7-component score. Default keeps the legacy behaviour
        # for every other saved search.
        score_field = (filters.get("score_field") or "score").strip()
        use_high_moat = score_field == "high_moat_score"
        use_cyber_scope = score_field == "cyber_scope_score"
        if use_cyber_scope:
            score_column = OpportunityScore.cyber_scope_score
        elif use_high_moat:
            score_column = OpportunityScore.high_moat_score
        else:
            score_column = OpportunityScore.score

        stmt = (
            select(OpportunityScore, OpportunityRaw)
            .join(OpportunityRaw, OpportunityRaw.id == OpportunityScore.opportunity_id)
            .where(
                OpportunityScore.tenant_id == tenant.id,
                score_column.is_not(None),
                score_column >= search.alert_threshold,
            )
            .order_by(score_column.desc())
            .limit(SAVED_SEARCH_HITS_CAP)
        )
        if naics_codes:
            stmt = stmt.where(OpportunityRaw.naics_code.in_(naics_codes))
        if set_asides:
            stmt = stmt.where(OpportunityRaw.set_aside.in_(set_asides))
        # Keyword ILIKE pre-filter is for general saved searches that don't
        # have a clause detector behind them. For the high-moat track the
        # high_moat_score column already encodes a much richer match (clause
        # detector + agency + velocity + set-aside + clearance) — adding a
        # title/description ILIKE here would discard UFGS hits buried only
        # in the PDF attachment_text.
        if keywords and not use_high_moat and not use_cyber_scope:
            keyword_filter = None
            for kw in keywords:
                like = f"%{kw}%"
                clause = OpportunityRaw.title.ilike(like) | OpportunityRaw.description_text.ilike(
                    like
                )
                keyword_filter = clause if keyword_filter is None else (keyword_filter | clause)
            stmt = stmt.where(keyword_filter)
        if search.last_delivered_at is not None:
            # Only show new scoring activity since the last digest delivery.
            stmt = stmt.where(OpportunityScore.scored_at > search.last_delivered_at)

        rows = (await session.execute(stmt)).all()
        if not rows:
            continue

        digest_rows: list[DigestRow] = []
        for sc, opp in rows:
            raw_payload = opp.raw_payload or {}
            if use_cyber_scope:
                row_score = sc.cyber_scope_score
            elif use_high_moat:
                row_score = sc.high_moat_score
            else:
                row_score = sc.score
            sweet_spot = bool(
                use_high_moat
                and (sc.high_moat_flags or {}).get("is_high_probability_easy_win")
            )
            digest_rows.append(
                DigestRow(
                    title=opp.title,
                    notice_type=opp.notice_type,
                    set_aside=opp.set_aside,
                    naics_code=opp.naics_code,
                    agency_short=_short_agency(opp.agency),
                    score=int(row_score or 0),
                    why_it_matters=(
                        # For high-moat rows, the seed line is more specific
                        # than the general why_it_matters paragraph.
                        ((sc.high_moat_flags or {}).get("why_it_matters_seed") or sc.why_it_matters)
                        if use_high_moat
                        else sc.why_it_matters
                    ),
                    incumbent_summary=None,
                    sam_link=raw_payload.get("uiLink"),
                    high_moat_score=sc.high_moat_score if use_high_moat else None,
                    is_sweet_spot=sweet_spot,
                )
            )
        out.append(
            SavedSearchHits(
                search_id=search.id,
                search_name=search.name,
                rows=digest_rows,
            )
        )

    return out


async def _stamp_saved_searches_delivered(
    session: AsyncSession, search_ids: list[UUID]
) -> None:
    if not search_ids:
        return
    now = datetime.now(UTC)
    await session.execute(
        SavedSearch.__table__.update()
        .where(SavedSearch.id.in_(search_ids))
        .values(last_delivered_at=now)
    )


async def _load_top_for_founder(
    session: AsyncSession, tenant: Tenant, founder: Founder, top_n: int
) -> list[DigestRow]:
    rows = (
        await session.execute(
            select(OpportunityScore, OpportunityRaw, OpportunityEnriched)
            .join(OpportunityRaw, OpportunityRaw.id == OpportunityScore.opportunity_id)
            .outerjoin(
                OpportunityEnriched,
                OpportunityEnriched.opportunity_id == OpportunityRaw.id,
            )
            .where(
                OpportunityScore.tenant_id == tenant.id,
                OpportunityScore.assigned_founder_id == founder.id,
                OpportunityScore.score >= MIN_SCORE_FOR_DIGEST,
            )
            .order_by(OpportunityScore.score.desc())
            .limit(top_n)
        )
    ).all()
    out: list[DigestRow] = []
    for sc, opp, enr in rows:
        raw_payload = opp.raw_payload or {}
        out.append(
            DigestRow(
                title=opp.title,
                notice_type=opp.notice_type,
                set_aside=opp.set_aside,
                naics_code=opp.naics_code,
                agency_short=_short_agency(opp.agency),
                score=sc.score,
                why_it_matters=sc.why_it_matters,
                incumbent_summary=_incumbent_one_liner(enr),
                sam_link=raw_payload.get("uiLink"),
            )
        )
    return out


def _render_search_block_html(hits: SavedSearchHits) -> str:
    items: list[str] = []
    for r in hits.rows:
        meta_bits = [
            r.notice_type or "",
            r.set_aside or "",
            f"NAICS {r.naics_code}" if r.naics_code else "",
            r.agency_short or "",
        ]
        meta = " · ".join(b for b in meta_bits if b)
        link = (
            f'<a href="{escape(r.sam_link)}" '
            f'style="color:#1a3a5c;font-size:13px">View on SAM.gov</a>'
            if r.sam_link
            else ""
        )
        # Sober "high-probability easy win" marker for high-moat rows
        # whose sweet-spot conditions all line up (UFGS 25 hit + construction
        # prime + active). No emoji per the playbook copy rules.
        sweet_marker = (
            '<span style="display:inline-block;background:#0b3d2e;color:#fff;'
            'font-size:10px;letter-spacing:.08em;text-transform:uppercase;'
            'padding:2px 8px;border-radius:3px;margin-left:8px;'
            'vertical-align:middle">High-Probability Easy Win</span>'
            if r.is_sweet_spot
            else ""
        )
        score_label = (
            f"high-moat {r.score}" if r.high_moat_score is not None else f"score {r.score}"
        )
        why_block = (
            f'<p style="margin:6px 0 0;color:#333;font-size:13px;line-height:1.5">'
            f"{escape(r.why_it_matters)}</p>"
            if r.why_it_matters
            else ""
        )
        items.append(
            f"""
            <div style="border:1px solid #e5e5e5;border-radius:6px;padding:12px 16px;margin-bottom:8px;background:#fff">
              <div style="font-size:12px;color:#666;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px">
                {score_label}{sweet_marker}
              </div>
              <div style="font-size:14px;font-weight:600;color:#111;margin:0 0 4px">{escape(r.title)}</div>
              <div style="font-size:12px;color:#888">{escape(meta)}</div>
              {why_block}
              <div style="margin-top:8px">{link}</div>
            </div>
            """.strip()
        )
    return (
        f'<div style="margin:18px 0 8px"><h2 style="font-size:14px;'
        f'margin:0 0 8px;color:#1a3a5c">'
        f"Saved search: {escape(hits.search_name)} · {len(hits.rows)} new hit"
        f"{'s' if len(hits.rows) != 1 else ''}</h2></div>"
        + "".join(items)
    )


def _render_html(
    founder: Founder,
    rows: list[DigestRow],
    saved_search_blocks: list[SavedSearchHits] | None = None,
) -> str:
    today = datetime.now(UTC).strftime("%A, %B %-d, %Y")
    items_html: list[str] = []
    for i, r in enumerate(rows, start=1):
        meta_bits = [
            r.notice_type or "",
            r.set_aside or "",
            f"NAICS {r.naics_code}" if r.naics_code else "",
            r.agency_short or "",
        ]
        meta = " · ".join(b for b in meta_bits if b)
        why = (
            f'<p style="margin:8px 0 0;color:#333;line-height:1.5">'
            f"{escape(r.why_it_matters)}</p>"
            if r.why_it_matters
            else ""
        )
        incumbent = (
            f'<p style="margin:6px 0 0;font-size:13px;color:#666">'
            f"<strong>Incumbent:</strong> {escape(r.incumbent_summary)}"
            f"</p>"
            if r.incumbent_summary
            else ""
        )
        link = (
            f'<a href="{escape(r.sam_link)}" '
            f'style="color:#1a3a5c;font-size:13px">View on SAM.gov</a>'
            if r.sam_link
            else ""
        )
        items_html.append(
            f"""
            <div style="border:1px solid #e5e5e5;border-radius:6px;padding:16px 20px;margin-bottom:12px;background:#fff">
              <div style="font-size:12px;color:#666;letter-spacing:.04em;text-transform:uppercase;margin-bottom:4px">
                #{i} · score {r.score}
              </div>
              <div style="font-size:15px;font-weight:600;color:#111;margin:0 0 4px">
                {escape(r.title)}
              </div>
              <div style="font-size:12px;color:#888">{escape(meta)}</div>
              {why}
              {incumbent}
              <div style="margin-top:10px">{link}</div>
            </div>
            """.strip()
        )
    items_block = "\n".join(items_html) if items_html else (
        '<p style="color:#666">No opportunities scored above the threshold today. '
        "Continuous SAM ingestion runs every 2 hours; check back tomorrow.</p>"
    )
    saved_search_html = ""
    for hits in saved_search_blocks or []:
        saved_search_html += _render_search_block_html(hits)
    if saved_search_html:
        items_block = items_block + saved_search_html

    return f"""<!doctype html>
<html><body style="margin:0;background:#fafafa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#111">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#fafafa">
  <tr><td align="center" style="padding:32px 16px">
    <table width="640" cellpadding="0" cellspacing="0" border="0" style="background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e5e5e5">
      <tr><td style="padding:24px 28px;border-bottom:1px solid #e5e5e5">
        <p style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#666;margin:0 0 4px">MacTech CaptureOS</p>
        <h1 style="font-size:20px;margin:0;color:#111">{escape(founder.full_name)} — {today}</h1>
        <p style="margin:4px 0 0;color:#666;font-size:13px">{escape(founder.pillar.title())} pillar · top {len(rows)} scored opportunities</p>
      </td></tr>
      <tr><td style="padding:20px 28px;background:#fafafa">
        {items_block}
      </td></tr>
      <tr><td style="padding:16px 28px;border-top:1px solid #e5e5e5;font-size:12px;color:#888">
        <p style="margin:0">MacTech Solutions LLC · SDVOSB-certified · Veteran-Owned</p>
        <p style="margin:4px 0 0">Replies go to patrick@mactechsolutionsllc.com</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _render_text(
    founder: Founder,
    rows: list[DigestRow],
    saved_search_blocks: list[SavedSearchHits] | None = None,
) -> str:
    today = datetime.now(UTC).strftime("%A, %B %-d, %Y")
    out = [f"MacTech CaptureOS — {today}", f"{founder.full_name} ({founder.pillar})"]
    out.append("")
    if not rows:
        out.append("No opportunities scored above the threshold today.")
        out.append("Continuous SAM ingestion runs every 2 hours.")
    for i, r in enumerate(rows, start=1):
        out.append(f"#{i}  score {r.score}")
        out.append(f"    {r.title}")
        meta_bits = [
            r.notice_type or "",
            r.set_aside or "",
            f"NAICS {r.naics_code}" if r.naics_code else "",
            r.agency_short or "",
        ]
        out.append(f"    {' · '.join(b for b in meta_bits if b)}")
        if r.incumbent_summary:
            out.append(f"    Incumbent: {r.incumbent_summary}")
        if r.why_it_matters:
            out.append("")
            out.append(f"    {r.why_it_matters}")
        if r.sam_link:
            out.append(f"    {r.sam_link}")
        out.append("")
    for hits in saved_search_blocks or []:
        out.append("")
        out.append(f"-- Saved search: {hits.search_name} ({len(hits.rows)} new) --")
        for r in hits.rows:
            label = (
                f"high-moat {r.score}" if r.high_moat_score is not None else f"score {r.score}"
            )
            tag = " [High-Probability Easy Win]" if r.is_sweet_spot else ""
            out.append(f"  {label}{tag}  {r.title}")
            if r.why_it_matters:
                out.append(f"    {r.why_it_matters}")
            if r.sam_link:
                out.append(f"    {r.sam_link}")
    out.append("")
    out.append("--")
    out.append("MacTech Solutions LLC · SDVOSB-certified · Veteran-Owned")
    return "\n".join(out)


async def send_digest_for_founder(
    founder_slug: str,
    *,
    tenant_slug: str | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> DigestSendStats:
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get(
        "RESEND_FROM", "MacTech CaptureOS <onboarding@resend.dev>"
    )
    reply_to = os.environ.get("RESEND_REPLY_TO") or None
    # Tenant scope: explicit param wins; falls back to MACTECH_TENANT_SLUG
    # env (legacy single-tenant default).
    if tenant_slug is None:
        tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")

    if not api_key:
        return DigestSendStats(
            founder_slug=founder_slug,
            founder_name="",
            recipient=None,
            items_count=0,
            saved_search_hit_count=0,
            sent=False,
            skipped_reason="RESEND_API_KEY not set",
            message_id=None,
        )

    session_factory = async_session_factory()
    async with session_factory() as session:
        # Resolve tenant first — founder slugs are now per-tenant unique,
        # not globally unique. The MACTECH_TENANT_SLUG env var pins the
        # worker to a single tenant; multi-tenant digest is a future sprint.
        from mactech_db.models import Tenant as _T

        tenant_row = (
            await session.execute(select(_T).where(_T.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant_row is None:
            return DigestSendStats(
                founder_slug=founder_slug,
                founder_name="",
                recipient=None,
                items_count=0,
                saved_search_hit_count=0,
                sent=False,
                skipped_reason=f"tenant {tenant_slug!r} not found",
                message_id=None,
            )
        founder = (
            await session.execute(
                select(Founder).where(
                    Founder.tenant_id == tenant_row.id,
                    Founder.slug == founder_slug,
                )
            )
        ).scalar_one_or_none()
        if founder is None:
            return DigestSendStats(
                founder_slug=founder_slug,
                founder_name="",
                recipient=None,
                items_count=0,
                saved_search_hit_count=0,
                sent=False,
                skipped_reason="founder not found",
                message_id=None,
            )
        if not founder.digest_enabled:
            return DigestSendStats(
                founder_slug=founder_slug,
                founder_name=founder.full_name,
                recipient=founder.email,
                items_count=0,
                saved_search_hit_count=0,
                sent=False,
                skipped_reason="digest_enabled=false",
                message_id=None,
            )
        if not founder.email:
            return DigestSendStats(
                founder_slug=founder_slug,
                founder_name=founder.full_name,
                recipient=None,
                items_count=0,
                saved_search_hit_count=0,
                sent=False,
                skipped_reason="no email on file",
                message_id=None,
            )
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one()
        rows = await _load_top_for_founder(session, tenant, founder, top_n)
        saved_hits = await _load_saved_search_hits(
            session, tenant=tenant, founder=founder
        )

    saved_total = sum(len(h.rows) for h in saved_hits)
    today = datetime.now(UTC).strftime("%a %b %-d")
    extra = (
        f" + {saved_total} saved-search hit{'s' if saved_total != 1 else ''}"
        if saved_total
        else ""
    )
    subject = (
        f"[MacTech Capture] {len(rows)} {founder.full_name.split()[0]} picks"
        f"{extra} for {today}"
    )
    html = _render_html(founder, rows, saved_hits)
    text = _render_text(founder, rows, saved_hits)

    async with ResendClient(api_key=api_key) as resend:
        try:
            result = await resend.send_email(
                from_addr=from_addr,
                to=[founder.email],
                subject=subject,
                html=html,
                text=text,
                reply_to=reply_to,
                tags=[
                    {"name": "kind", "value": "founder_digest"},
                    {"name": "founder", "value": founder.slug},
                ],
            )
        except ResendError as exc:
            log.warning("digest send failed for %s: %s", founder.slug, exc)
            return DigestSendStats(
                founder_slug=founder_slug,
                founder_name=founder.full_name,
                recipient=founder.email,
                items_count=len(rows),
                saved_search_hit_count=saved_total,
                sent=False,
                skipped_reason=f"resend error: {exc!s}"[:300],
                message_id=None,
            )

    # Mark each saved search that contributed hits as delivered. Uses a
    # fresh session — async_session_factory()() produces a new one — so
    # we don't depend on the prior `with` block still being open.
    if saved_hits:
        async with session_factory() as session2:
            await _stamp_saved_searches_delivered(
                session2, [h.search_id for h in saved_hits]
            )
            await session2.commit()

    log.info(
        "digest sent founder=%s recipient=%s items=%d saved_hits=%d msg=%s",
        founder.slug,
        founder.email,
        len(rows),
        saved_total,
        result.message_id,
    )
    return DigestSendStats(
        founder_slug=founder_slug,
        founder_name=founder.full_name,
        recipient=founder.email,
        items_count=len(rows),
        saved_search_hit_count=saved_total,
        sent=True,
        skipped_reason=None,
        message_id=result.message_id,
    )


async def send_digest_to_all_founders(
    *,
    only_tenant_slug: str | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> list[DigestSendStats]:
    """Fan out the morning digest across every tenant.

    For each tenant: pull every digest_enabled founder, send to each.
    Errors per-founder are caught and surfaced as DigestSendStats with
    sent=False rather than aborting the loop.

    `only_tenant_slug` (or the legacy MACTECH_TENANT_SLUG env var) pins
    the run to a single tenant — useful for testing or for single-tenant
    deployments. When neither is set, fan out across all tenants.
    """
    pin = only_tenant_slug or os.environ.get("MACTECH_PIN_TENANT_SLUG") or None
    session_factory = async_session_factory()
    async with session_factory() as session:
        from mactech_db.models import Tenant as _T

        stmt = select(_T)
        if pin:
            stmt = stmt.where(_T.slug == pin)
        else:
            # Stable order so the run is reproducible across deploys.
            stmt = stmt.order_by(_T.slug)
        tenants = (await session.execute(stmt)).scalars().all()

        # Pre-load all (tenant_id → list[Founder]) in one query.
        all_founders = (
            await session.execute(
                select(Founder).where(Founder.digest_enabled.is_(True))
            )
        ).scalars().all()

    by_tenant: dict[UUID, list[Founder]] = {}
    for f in all_founders:
        by_tenant.setdefault(f.tenant_id, []).append(f)

    results: list[DigestSendStats] = []
    for t in tenants:
        for f in by_tenant.get(t.id, []):
            try:
                stats = await send_digest_for_founder(
                    f.slug, tenant_slug=t.slug, top_n=top_n
                )
            except Exception as exc:  # noqa: BLE001 — per-founder failure shouldn't abort fan-out
                log.exception(
                    "digest send_all failed for tenant=%s founder=%s: %s",
                    t.slug,
                    f.slug,
                    exc,
                )
                stats = DigestSendStats(
                    founder_slug=f.slug,
                    founder_name=f.full_name,
                    recipient=f.email,
                    items_count=0,
                    saved_search_hit_count=0,
                    sent=False,
                    skipped_reason=f"unexpected error: {exc.__class__.__name__}",
                    message_id=None,
                )
            results.append(stats)
    return results


@celery_app.task(name="mactech.digest.send_all")
def send_digest_all_task(top_n: int = DEFAULT_TOP_N) -> list[dict[str, object]]:
    return [asdict(s) for s in asyncio.run(send_digest_to_all_founders(top_n=top_n))]


@celery_app.task(name="mactech.digest.send_one")
def send_digest_one_task(
    founder_slug: str, top_n: int = DEFAULT_TOP_N
) -> dict[str, object]:
    return asdict(asyncio.run(send_digest_for_founder(founder_slug, top_n=top_n)))
