"""Pack-driven multi-family signal detector.

Scans text against every enabled knowledge-pack concept (all families, not just
the legacy detector categories), plus normalized UFGS/DFARS identifiers. Returns
evidence-bearing ``SignalHit``s the decision engine (Slice 4) consumes for the
decision vector and gates. Deterministic — no LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mactech_intelligence.cyber_scope.regex_utils import (
    compile_literal_patterns,
    compile_regex_pattern,
    surrounding_text,
)
from mactech_intelligence.detection.identifiers import IdentifierHit, find_identifiers
from mactech_intelligence.knowledge.pack import Concept, load_pack


@dataclass(frozen=True)
class SignalHit:
    concept_id: str
    family: str
    evidence_category: str | None
    canonical_name: str
    normalized_term: str
    weight: int
    negative_weight: int
    disqualifier: bool
    gate_code: str | None
    severity: str | None
    match_type: str  # "REGEX" | "LITERAL" | "IDENTIFIER"
    snippet: str
    start: int
    end: int


@dataclass
class SignalReport:
    hits: list[SignalHit] = field(default_factory=list)
    identifiers: list[IdentifierHit] = field(default_factory=list)
    pack_version: str = ""

    @property
    def by_family(self) -> dict[str, list[SignalHit]]:
        out: dict[str, list[SignalHit]] = {}
        for h in self.hits:
            out.setdefault(h.family, []).append(h)
        return out

    @property
    def disqualifiers(self) -> list[SignalHit]:
        return [h for h in self.hits if h.disqualifier]

    def families_present(self) -> set[str]:
        return {h.family for h in self.hits}

    def has_family(self, family: str) -> bool:
        return any(h.family == family for h in self.hits)

    def _has_category(self, categories: set[str]) -> bool:
        return any(h.evidence_category in categories for h in self.hits)

    @property
    def has_direct_cyber(self) -> bool:
        return self._has_category(
            {"rmf_ato_emass", "nist_cnssi_fips", "far_dfars_cmmc", "direct_cyber"}
        )

    @property
    def has_frcs_ot(self) -> bool:
        return self._has_category({"ufc_frcs", "ot_ics_scada_pit"})

    @property
    def has_facility_adjacency(self) -> bool:
        return self._has_category({"facility_adjacency"})

    @property
    def has_training(self) -> bool:
        return self._has_category({"training"})

    @property
    def has_acquisition_context(self) -> bool:
        return self._has_category({"acquisition_context"})

    @property
    def relevance_weight(self) -> int:
        return sum(h.weight for h in self.hits if not h.disqualifier)

    def barriers_by_severity(self) -> tuple[frozenset[str], frozenset[str]]:
        """(hard_gate_codes, soft_gate_codes) from detected disqualifiers."""
        hard: set[str] = set()
        soft: set[str] = set()
        for h in self.disqualifiers:
            if not h.gate_code:
                continue
            (hard if h.severity == "hard" else soft).add(h.gate_code)
        return frozenset(hard), frozenset(soft)


def _regex_from_concept(concept: Concept) -> re.Pattern[str] | None:
    if not concept.regex:
        return None
    regex = concept.regex.strip("/")
    if regex.endswith("/i"):
        regex = regex[:-2]
    return compile_regex_pattern(regex)


def _match_concept(text: str, concept: Concept) -> SignalHit | None:
    compiled = _regex_from_concept(concept)
    if compiled is not None:
        m = compiled.search(text)
        if m is None:
            return None
        return _hit(concept, "REGEX", text, m.start(), m.end())

    for pat in compile_literal_patterns(list(concept.match_patterns)):
        m = pat.search(text)
        if m is not None:
            return _hit(concept, "LITERAL", text, m.start(), m.end())
    return None


def _hit(concept: Concept, match_type: str, text: str, start: int, end: int) -> SignalHit:
    return SignalHit(
        concept_id=concept.id,
        family=concept.family,
        evidence_category=concept.evidence_category,
        canonical_name=concept.canonical_name,
        normalized_term=concept.normalized_term,
        weight=concept.positive_weight,
        negative_weight=concept.negative_weight,
        disqualifier=concept.disqualifier,
        gate_code=concept.gate_code,
        severity=concept.severity,
        match_type=match_type,
        snippet=surrounding_text(text, start, end),
        start=start,
        end=end,
    )


def detect_signals(text: str) -> SignalReport:
    """Detect all enabled pack concepts + normalized identifiers in text."""
    pack = load_pack()
    report = SignalReport(pack_version=pack.pack_version)
    if not text:
        return report

    for concept in pack.concepts:
        hit = _match_concept(text, concept)
        if hit is not None:
            report.hits.append(hit)

    report.identifiers = find_identifiers(text)
    return report
