"""SEC EDGAR distress signals for top-N federal contractors.

Sprint 22 / strategy doc §3.3. Weekly Sunday 1800 ET beat:

  1. Pull top N contractors by total obligated $ from awards_history.
  2. Look up SEC CIK via the company_tickers.json dump (matches on
     company name → ticker → CIK).
  3. For each match, fetch recent filings via data.sec.gov.
  4. Compute a heuristic distress_score from filings cadence + 8-K
     item codes (1.05 going-concern, 2.05 material restructuring,
     5.02 director/officer departures, 8.01 other material events).
  5. Upsert into incumbent_signals.

This is the first cut — Phase 2 will add Claude extraction of the
filing prose for richer summaries. Phase 1 ships the metadata-only
signal which is already actionable on the recompete card.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from mactech_db import unscoped_session
from mactech_db.models import AwardHistory, IncumbentSignal
from mactech_integrations.sec_edgar import EdgarClient, EdgarError
from mactech_workers.celery_app import celery_app

log = logging.getLogger(__name__)

DEFAULT_TOP_N = 200

# 8-K items that historically correlate with distress / change-of-control.
# https://www.sec.gov/forms/8K — item code reference.
_DISTRESS_8K_ITEMS = {
    "1.03": "bankruptcy or receivership",
    "1.05": "material cybersecurity incidents",
    "2.04": "triggering events that accelerate financial obligations",
    "2.05": "costs associated with exit/disposal activities",
    "2.06": "material impairments",
    "4.02": "non-reliance on previously issued financials",
    "5.02": "departure of directors / officers",
    "5.03": "amendment of bylaws / change in fiscal year",
    "8.01": "other material events",
}


@dataclass
class EdgarSignalsStats:
    fetched_contractors: int
    matched_cik: int
    distress_flagged: int
    upserted: int
    error: str | None
    duration_ms: int


@celery_app.task(name="mactech.edgar.refresh_top_contractors")
def refresh_top_contractors_task(top_n: int = DEFAULT_TOP_N) -> dict[str, Any]:
    return asdict(asyncio.run(_refresh(top_n=top_n)))


async def _refresh(*, top_n: int) -> EdgarSignalsStats:
    started = datetime.now(UTC)

    user_agent = os.environ.get(
        "EDGAR_USER_AGENT", "MacTech CaptureOS edgar-monitor support@mactechsolutionsllc.com"
    )

    # Pull top contractors by total obligations.
    async with unscoped_session() as session:
        rows = (
            await session.execute(
                select(
                    AwardHistory.recipient_uei,
                    AwardHistory.recipient_name,
                    func.sum(AwardHistory.obligated_amount).label("total"),
                    func.count(AwardHistory.id).label("award_count"),
                )
                .where(AwardHistory.recipient_name.is_not(None))
                .group_by(AwardHistory.recipient_uei, AwardHistory.recipient_name)
                .order_by(desc("total"))
                .limit(top_n)
            )
        ).all()

    if not rows:
        return EdgarSignalsStats(
            fetched_contractors=0,
            matched_cik=0,
            distress_flagged=0,
            upserted=0,
            error="awards_history empty — nothing to refresh",
            duration_ms=_ms(started),
        )

    matched_cik = 0
    distress_flagged = 0
    upserted = 0

    async with EdgarClient(user_agent=user_agent) as edgar:
        try:
            tickers = await edgar.fetch_company_tickers()
        except EdgarError as exc:
            log.warning("EDGAR ticker fetch failed: %s", exc)
            return EdgarSignalsStats(
                fetched_contractors=len(rows),
                matched_cik=0,
                distress_flagged=0,
                upserted=0,
                error=f"EDGAR ticker fetch: {exc}",
                duration_ms=_ms(started),
            )

        # Build name → CIK lookup (lowercase, normalized).
        name_to_cik: dict[str, dict] = {}
        for entry in tickers.values():
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            name_to_cik[_normalize_name(title)] = entry

        async with unscoped_session() as session:
            for r in rows:
                display_name = r.recipient_name.strip()
                normalized = _normalize_name(display_name)
                match = _best_cik_match(normalized, name_to_cik)

                if not match:
                    # Persist a row even without CIK so we know we
                    # checked. Recompete UI will show "no public
                    # filings" for these.
                    _ = await _upsert_signal(
                        session,
                        normalized=normalized,
                        display=display_name,
                        recipient_uei=r.recipient_uei,
                        cik=None,
                        ticker=None,
                        title=None,
                        filings=[],
                    )
                    upserted += 1
                    continue

                matched_cik += 1
                cik = str(match.get("cik_str") or match.get("cik") or "")
                ticker = match.get("ticker")
                title = match.get("title")

                try:
                    filings = await edgar.fetch_recent_filings(cik)
                except EdgarError as exc:
                    log.info("EDGAR filings fetch failed for %s: %s", display_name, exc)
                    filings = []

                signal_score, summary = _score_filings(filings)
                if signal_score > 0:
                    distress_flagged += 1

                _ = await _upsert_signal(
                    session,
                    normalized=normalized,
                    display=display_name,
                    recipient_uei=r.recipient_uei,
                    cik=cik,
                    ticker=ticker,
                    title=title,
                    filings=filings,
                    distress_score=signal_score,
                    distress_summary=summary,
                )
                upserted += 1

    log.info(
        "edgar_signals: contractors=%d matched_cik=%d distress=%d upserted=%d",
        len(rows),
        matched_cik,
        distress_flagged,
        upserted,
    )
    return EdgarSignalsStats(
        fetched_contractors=len(rows),
        matched_cik=matched_cik,
        distress_flagged=distress_flagged,
        upserted=upserted,
        error=None,
        duration_ms=_ms(started),
    )


async def _upsert_signal(
    session,
    *,
    normalized: str,
    display: str,
    recipient_uei: str | None,
    cik: str | None,
    ticker: str | None,
    title: str | None,
    filings: list,
    distress_score: int = 0,
    distress_summary: str | None = None,
) -> None:
    today = datetime.now(UTC).date()
    cutoff_90 = today - timedelta(days=90)
    cutoff_365 = today - timedelta(days=365)

    last_90 = 0
    last_365 = 0
    most_recent_form: str | None = None
    most_recent_date: date | None = None
    most_recent_items: list[str] | None = None
    surface_filings: list[dict] = []

    for f in filings[:10]:  # surface display
        try:
            f_date = date.fromisoformat(f.filing_date) if f.filing_date else None
        except ValueError:
            f_date = None
        surface_filings.append(
            {
                "form": f.form,
                "filing_date": f.filing_date,
                "accession": f.accession_number,
                "items": f.items,
                "url": f.primary_doc_url,
            }
        )
        if f_date:
            if f_date >= cutoff_90:
                last_90 += 1
            if f_date >= cutoff_365:
                last_365 += 1
            if most_recent_date is None or f_date > most_recent_date:
                most_recent_date = f_date
                most_recent_form = f.form
                most_recent_items = list(f.items) if f.form == "8-K" else None

    stmt = (
        pg_insert(IncumbentSignal)
        .values(
            normalized_name=normalized,
            display_name=display[:255],
            recipient_uei=recipient_uei,
            cik=cik,
            sec_ticker=ticker,
            sec_title=title,
            filings_last_90d_count=last_90,
            filings_last_365d_count=last_365,
            most_recent_filing_form=most_recent_form,
            most_recent_filing_date=most_recent_date,
            most_recent_8k_items=most_recent_items,
            distress_score=distress_score,
            distress_summary=distress_summary,
            filings=surface_filings or None,
            last_refreshed_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["normalized_name"],
            set_={
                "display_name": display[:255],
                "recipient_uei": recipient_uei,
                "cik": cik,
                "sec_ticker": ticker,
                "sec_title": title,
                "filings_last_90d_count": last_90,
                "filings_last_365d_count": last_365,
                "most_recent_filing_form": most_recent_form,
                "most_recent_filing_date": most_recent_date,
                "most_recent_8k_items": most_recent_items,
                "distress_score": distress_score,
                "distress_summary": distress_summary,
                "filings": surface_filings or None,
                "last_refreshed_at": datetime.now(UTC),
            },
        )
    )
    await session.execute(stmt)


def _normalize_name(name: str) -> str:
    """Strip corporate suffixes + punctuation to maximize CIK match
    recall. CACI International Inc. and CACI Inc. should both match."""
    s = name.lower()
    s = re.sub(r"[,\.\(\)\[\]&]+", " ", s)
    suffixes = (
        r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|"
        r"holdings|group|technologies|technology|services|solutions|"
        r"systems|federal|government)\b"
    )
    s = re.sub(suffixes, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _best_cik_match(normalized: str, lookup: dict[str, dict]) -> dict | None:
    """Try exact normalized name first; then prefix; then containment.
    Skip very short normalized strings that would over-match."""
    if not normalized or len(normalized) < 3:
        return None
    if normalized in lookup:
        return lookup[normalized]
    # Prefix: many SEC titles are longer than the federal awardee name.
    for k, v in lookup.items():
        if k.startswith(normalized):
            return v
    # Reverse prefix: federal awardee may be a longer subsidiary form.
    for k, v in lookup.items():
        if normalized.startswith(k) and len(k) >= 5:
            return v
    return None


def _score_filings(filings: list) -> tuple[int, str | None]:
    """Heuristic 0..100. Inputs: filings cadence + 8-K item codes."""
    if not filings:
        return 0, None
    today = date.today()
    cutoff_90 = today - timedelta(days=90)
    last_90 = 0
    distress_items: set[str] = set()
    for f in filings:
        try:
            d = date.fromisoformat(f.filing_date) if f.filing_date else None
        except ValueError:
            d = None
        if d and d >= cutoff_90:
            last_90 += 1
            if f.form == "8-K":
                for item in f.items:
                    if item in _DISTRESS_8K_ITEMS:
                        distress_items.add(item)

    # Cadence component: more 8-Ks/quarter than usual = stress.
    cadence = min(40, last_90 * 8)  # cap at 40 from cadence
    item_score = min(60, len(distress_items) * 20)  # cap at 60 from items
    total = min(100, cadence + item_score)

    if not distress_items and last_90 == 0:
        return 0, None

    summary_bits: list[str] = []
    if last_90:
        summary_bits.append(f"{last_90} filing{'s' if last_90 != 1 else ''} in last 90d")
    if distress_items:
        labels = [f"item {i} ({_DISTRESS_8K_ITEMS[i]})" for i in sorted(distress_items)]
        summary_bits.append(f"recent 8-K signals: {', '.join(labels)}")
    return total, "; ".join(summary_bits) or None


def _ms(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)
