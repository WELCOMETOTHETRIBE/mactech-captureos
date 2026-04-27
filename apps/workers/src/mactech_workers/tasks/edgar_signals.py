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

# 8-K item codes that genuinely signal contractor distress.
# https://www.sec.gov/forms/8K — item code reference.
#
# NOT included (too noisy on the federal-contractor surface):
#   5.02 director/officer departure  — ordinary board hygiene, fires
#                                       constantly across every public
#                                       company in the watchlist
#   5.03 amendment of bylaws         — administrative
#   8.01 other material events       — generic catchall, weak signal
_DISTRESS_8K_ITEMS = {
    "1.03": "bankruptcy or receivership",
    "1.05": "material cybersecurity incident",
    "2.04": "triggering events that accelerate financial obligations",
    "2.05": "costs associated with exit/disposal activities",
    "2.06": "material impairments",
    "3.01": "notice of delisting or failure to satisfy listing rule",
    "4.01": "changes in registrant's certifying accountant",
    "4.02": "non-reliance on previously issued financials",
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


def _name_trigrams(s: str) -> set[str]:
    """3-character shingles for fuzzy matching, padded with leading
    space so word starts dominate."""
    s = " " + s.strip()
    if len(s) < 3:
        return set()
    return {s[i : i + 3] for i in range(len(s) - 2)}


def _trigram_similarity(a: str, b: str) -> float:
    ta = _name_trigrams(a)
    tb = _name_trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_MIN_NORMALIZED_LEN = 5  # short names like "ge" or "att" are too ambiguous
_MIN_TRIGRAM_SIM = 0.78  # rejects "Advantage Solutions" vs "Advantaged Solutions"


def _best_cik_match(normalized: str, lookup: dict[str, dict]) -> dict | None:
    """Find the best CIK match for a normalized federal-contractor name.

    Earlier version did exact → prefix → reverse-prefix substring which
    produced false positives like:
      "advantaged solutions" → "ADV" (Advantage Solutions Inc, marketing co)
      "global integrated"    → "GIS" (General Mills, food co)

    Now requires:
      1. exact match, OR
      2. trigram similarity >= 0.78 against ALL candidate names

    The exact path stays — most top federal contractors (caci, leidos,
    saic, l3harris, parsons, fluor, etc.) match exactly after corporate-
    suffix stripping. The trigram fallback catches verbose/subsidiary
    variants like "fluor federal petroleum operations" against "fluor
    corp" without admitting marketing-firm collisions.
    """
    if not normalized or len(normalized) < _MIN_NORMALIZED_LEN:
        return None
    if normalized in lookup:
        return lookup[normalized]
    best_score = 0.0
    best_match: dict | None = None
    for k, v in lookup.items():
        if len(k) < _MIN_NORMALIZED_LEN:
            continue
        sim = _trigram_similarity(normalized, k)
        if sim > best_score:
            best_score = sim
            best_match = v
    if best_score >= _MIN_TRIGRAM_SIM:
        return best_match
    return None


def _score_filings(filings: list) -> tuple[int, str | None]:
    """Heuristic 0..100. Score only fires when there's an actual
    distress 8-K item (1.03/1.05/2.04/2.05/2.06/3.01/4.01/4.02) OR
    abnormally high filings cadence (>10 in 90d). Plain "company filed
    its quarterly + a few 8-Ks for routine board matters" → 0.

    This intentionally leaves "no signal" as the default so the 🚩 flag
    on the recompete card means something when it appears.
    """
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

    has_distress_items = bool(distress_items)
    abnormal_cadence = last_90 > 10
    if not has_distress_items and not abnormal_cadence:
        return 0, None

    # 70 from each item (capped at 100 — even one of these is loud), +5 per
    # filing over the cadence threshold (max +30).
    item_score = min(100, 70 if has_distress_items else 0)
    cadence_bonus = max(0, last_90 - 10) * 5 if abnormal_cadence else 0
    total = min(100, item_score + cadence_bonus)

    summary_bits: list[str] = []
    if distress_items:
        labels = [f"item {i} ({_DISTRESS_8K_ITEMS[i]})" for i in sorted(distress_items)]
        summary_bits.append(f"recent 8-K: {', '.join(labels)}")
    if abnormal_cadence:
        summary_bits.append(f"unusual filings cadence ({last_90} in 90d)")
    return total, "; ".join(summary_bits) or None


def _ms(started: datetime) -> int:
    return int((datetime.now(UTC) - started).total_seconds() * 1000)
