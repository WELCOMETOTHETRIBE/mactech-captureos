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
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import (
    Founder,
    OpportunityEnriched,
    OpportunityRaw,
    OpportunityScore,
    Tenant,
)
from mactech_integrations.resend import ResendClient, ResendError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_TOP_N = 5
MIN_SCORE_FOR_DIGEST = 60


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


@dataclass
class DigestSendStats:
    founder_slug: str
    founder_name: str
    recipient: str | None
    items_count: int
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


def _render_html(founder: Founder, rows: list[DigestRow]) -> str:
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
        <p style="margin:0">MacTech Solutions LLC · SDVOSB (pending) · Veteran-Owned</p>
        <p style="margin:4px 0 0">Replies go to patrick@mactechsolutionsllc.com</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def _render_text(founder: Founder, rows: list[DigestRow]) -> str:
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
    out.append("--")
    out.append("MacTech Solutions LLC · SDVOSB (pending) · Veteran-Owned")
    return "\n".join(out)


async def send_digest_for_founder(
    founder_slug: str, *, top_n: int = DEFAULT_TOP_N
) -> DigestSendStats:
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get(
        "RESEND_FROM", "MacTech CaptureOS <onboarding@resend.dev>"
    )
    reply_to = os.environ.get("RESEND_REPLY_TO") or None
    tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")

    if not api_key:
        return DigestSendStats(
            founder_slug=founder_slug,
            founder_name="",
            recipient=None,
            items_count=0,
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
                sent=False,
                skipped_reason="no email on file",
                message_id=None,
            )
        tenant = (
            await session.execute(select(Tenant).where(Tenant.slug == tenant_slug))
        ).scalar_one()
        rows = await _load_top_for_founder(session, tenant, founder, top_n)

    today = datetime.now(UTC).strftime("%a %b %-d")
    subject = f"[MacTech Capture] {len(rows)} new {founder.full_name.split()[0]} picks for {today}"
    html = _render_html(founder, rows)
    text = _render_text(founder, rows)

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
                sent=False,
                skipped_reason=f"resend error: {exc!s}"[:300],
                message_id=None,
            )

    log.info(
        "digest sent founder=%s recipient=%s items=%d msg=%s",
        founder.slug,
        founder.email,
        len(rows),
        result.message_id,
    )
    return DigestSendStats(
        founder_slug=founder_slug,
        founder_name=founder.full_name,
        recipient=founder.email,
        items_count=len(rows),
        sent=True,
        skipped_reason=None,
        message_id=result.message_id,
    )


async def send_digest_to_all_founders(*, top_n: int = DEFAULT_TOP_N) -> list[DigestSendStats]:
    """Send to every digest-enabled founder in the MACTECH_TENANT_SLUG tenant.

    Multi-tenant fan-out (one digest per tenant) is a future sprint —
    today the worker is pinned to a single tenant via env var.
    """
    tenant_slug = os.environ.get("MACTECH_TENANT_SLUG", "mactech")
    session_factory = async_session_factory()
    async with session_factory() as session:
        from mactech_db.models import Tenant as _T

        tenant_row = (
            await session.execute(select(_T).where(_T.slug == tenant_slug))
        ).scalar_one_or_none()
        if tenant_row is None:
            return []
        founders = (
            await session.execute(
                select(Founder).where(
                    Founder.tenant_id == tenant_row.id,
                    Founder.digest_enabled.is_(True),
                )
            )
        ).scalars().all()
    results: list[DigestSendStats] = []
    for f in founders:
        stats = await send_digest_for_founder(f.slug, top_n=top_n)
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
