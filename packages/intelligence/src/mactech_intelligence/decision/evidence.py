"""Evidence assembly for LLM adjudication (Slice 5).

Turns deterministic detections into a ranked list of evidence items, each with a
STABLE id — ``ev:`` + sha1(doc_hash + ordinal + normalized_term)[:10]. The same
detection always gets the same id, so the LLM's citations are checkable and
reproducible. The id set is the allow-list the validator enforces.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from mactech_intelligence.detection.signals import SignalReport


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    family: str
    canonical_name: str
    normalized_term: str
    weight: int
    snippet: str


def _evidence_id(doc_hash: str, ordinal: int, normalized_term: str) -> str:
    raw = f"{doc_hash}:{ordinal}:{normalized_term}".encode()
    return "ev:" + hashlib.sha1(raw).hexdigest()[:10]


def assemble_evidence(
    report: SignalReport, *, doc_hash: str, limit: int = 24
) -> list[EvidenceItem]:
    """Rank detections by weight, dedupe by concept, and assign stable ids."""
    seen: set[str] = set()
    ranked = sorted(report.hits, key=lambda h: h.weight, reverse=True)
    items: list[EvidenceItem] = []
    for i, h in enumerate(ranked):
        if h.concept_id in seen:
            continue
        seen.add(h.concept_id)
        items.append(
            EvidenceItem(
                evidence_id=_evidence_id(doc_hash, i, h.normalized_term),
                family=h.family,
                canonical_name=h.canonical_name,
                normalized_term=h.normalized_term,
                weight=h.weight,
                snippet=h.snippet[:180],
            )
        )
        if len(items) >= limit:
            break
    return items


def evidence_id_set(items: list[EvidenceItem]) -> set[str]:
    return {it.evidence_id for it in items}
