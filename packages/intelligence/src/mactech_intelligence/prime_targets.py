"""Prime-target ranking (Slice 7).

Given the recent federal awardees for work like an opportunity's (from
USASpending), rank the companies MacTech would team under as a specialty cyber
sub. Pure and deterministic — the worker fetches awards and persists; this
module only shapes and ranks, so it is unit-testable without the network.

Never fabricates a company, contact, or award — every candidate is backed by
real award rows, and confidence reflects how much evidence there is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# USASpending award types: A/B/C/D are contracts.
TARGET_TYPES = (
    "incumbent",
    "historical_awardee",
    "likely_bidder",
    "vehicle_holder",
    "local_prime",
    "controls_integrator",
)

CONFIDENCE_LEVELS = ("confirmed", "probable", "possible", "unknown")


@dataclass(frozen=True)
class AwardRow:
    """A single USASpending award, reduced to what the ranker needs."""

    recipient_name: str | None
    recipient_uei: str | None
    award_id: str | None
    award_amount: float | None
    awarding_agency: str | None
    naics_code: str | None


@dataclass
class PrimeTargetCandidate:
    name: str
    uei: str | None
    target_type: str
    agencies: list[str]
    naics_codes: list[str]
    recent_award_ids: list[str]
    total_recent_award_amount: float
    award_count: int
    why_target: str
    recommended_contact_role: str
    confidence: str
    evidence: list[dict] = field(default_factory=list)


def _norm_name(name: str | None) -> str:
    return (name or "").strip().upper()


def _confidence_for(award_count: int, total_amount: float) -> str:
    # More awards + more dollars => more confident this firm is a real player
    # for this kind of work at this customer. Never "confirmed" from awards
    # alone (that requires naming them the actual incumbent on THIS notice).
    if award_count >= 4 and total_amount >= 5_000_000:
        return "probable"
    if award_count >= 2:
        return "probable"
    if award_count == 1:
        return "possible"
    return "unknown"


def rank_prime_targets(
    awards: list[AwardRow],
    *,
    recommended_contact_role: str = "capture manager / small-business liaison officer",
    limit: int = 8,
) -> list[PrimeTargetCandidate]:
    """Aggregate awards by recipient and rank by recent dollar volume."""
    by_key: dict[str, dict] = {}
    for a in awards:
        key = a.recipient_uei or _norm_name(a.recipient_name)
        if not key:
            continue
        slot = by_key.setdefault(
            key,
            {
                "name": a.recipient_name or key,
                "uei": a.recipient_uei,
                "agencies": set(),
                "naics": set(),
                "award_ids": [],
                "total": 0.0,
                "count": 0,
                "evidence": [],
            },
        )
        if a.awarding_agency:
            slot["agencies"].add(a.awarding_agency)
        if a.naics_code:
            slot["naics"].add(a.naics_code)
        if a.award_id and a.award_id not in slot["award_ids"]:
            slot["award_ids"].append(a.award_id)
        amt = float(a.award_amount or 0)
        slot["total"] += amt
        slot["count"] += 1
        if len(slot["evidence"]) < 5:
            slot["evidence"].append(
                {
                    "award_id": a.award_id,
                    "amount": amt,
                    "agency": a.awarding_agency,
                    "naics": a.naics_code,
                    "source": "usaspending",
                }
            )

    candidates: list[PrimeTargetCandidate] = []
    for slot in by_key.values():
        conf = _confidence_for(slot["count"], slot["total"])
        agencies = sorted(slot["agencies"])
        why = (
            f"{slot['count']} recent federal award(s) totaling "
            f"${slot['total']:,.0f}"
            + (f" at {agencies[0]}" if agencies else "")
            + " for like work — a realistic prime to team under."
        )
        candidates.append(
            PrimeTargetCandidate(
                name=slot["name"],
                uei=slot["uei"],
                target_type="historical_awardee",
                agencies=agencies,
                naics_codes=sorted(slot["naics"]),
                recent_award_ids=slot["award_ids"][:10],
                total_recent_award_amount=round(slot["total"], 2),
                award_count=slot["count"],
                why_target=why,
                recommended_contact_role=recommended_contact_role,
                confidence=conf,
                evidence=slot["evidence"],
            )
        )

    candidates.sort(key=lambda c: c.total_recent_award_amount, reverse=True)
    return candidates[:limit]
