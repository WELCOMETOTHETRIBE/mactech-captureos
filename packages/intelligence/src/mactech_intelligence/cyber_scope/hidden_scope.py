"""Hidden cyber scope detection — construction title + control-system specs."""

from __future__ import annotations

import re

from mactech_intelligence.cyber_scope.dictionary import load_construction_signals
from mactech_intelligence.cyber_scope.schemas import DetectionResult


def _has_construction_context(blob: str) -> bool:
    lower = blob.lower()
    return any(sig.lower() in lower for sig in load_construction_signals())


def _title_looks_non_cyber(title: str | None) -> bool:
    if not title:
        return True
    lower = title.lower()
    if "cyber" in lower or "security" in lower or "rmf" in lower:
        return False
    return True


def detect_hidden_scope(
    *,
    title: str | None,
    text: str,
    ufgs_hits: list[DetectionResult],
    dict_hits: dict[str, list[DetectionResult]],
) -> list[DetectionResult]:
    indicators: list[DetectionResult] = []
    blob = f"{title or ''} {text}"
    if not _has_construction_context(blob):
        return indicators

    tier2_4 = [h for h in ufgs_hits if h.ufgs_tier in (2, 4)]
    tier1 = [h for h in ufgs_hits if h.ufgs_tier == 1]
    ot_hits = dict_hits.get("ot_ics_scada_pit", [])
    rmf_hits = dict_hits.get("rmf_ato_emass", [])

    if tier2_4 and not tier1 and _title_looks_non_cyber(title):
        for h in tier2_4[:3]:
            indicators.append(
                DetectionResult(
                    term=h.term,
                    normalized_term=h.normalized_term,
                    category="hidden_scope",
                    confidence=0.85,
                    weight=10,
                    match_type="EXACT",
                    surrounding_text=h.surrounding_text
                    or "Construction/facilities scope with control-system UFGS but no explicit cyber title.",
                    ufgs=h.ufgs,
                    ufgs_tier=h.ufgs_tier,
                )
            )

    if ot_hits and rmf_hits and _title_looks_non_cyber(title):
        indicators.append(
            DetectionResult(
                term="OT/ICS + RMF in non-cyber title",
                normalized_term="hidden_ot_rmf",
                category="hidden_scope",
                confidence=0.8,
                weight=10,
                match_type="EXACT",
                surrounding_text="Facility/OT language paired with RMF/ATO requirements.",
            )
        )

    if re.search(r"\b(MILCON|USACE|NAVFAC)\b", blob, re.I) and (
        tier2_4 or dict_hits.get("ufc_frcs")
    ):
        indicators.append(
            DetectionResult(
                term="DoD construction + control systems",
                normalized_term="dod_construction_controls",
                category="hidden_scope",
                confidence=0.75,
                weight=8,
                match_type="EXACT",
                surrounding_text="DoD facilities construction with embedded control-system cyber scope.",
            )
        )

    return indicators
