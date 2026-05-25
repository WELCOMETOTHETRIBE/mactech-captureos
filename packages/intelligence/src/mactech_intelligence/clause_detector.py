"""Clause / clearance / role text detector for the high-moat scoring track.

Scans the union of title + description_text + attachment_text for:

* UFGS 25 05 11 / 25 08 11 (and broader Division 25) references — the
  headline buy signal for OT/ICS cyber work mandated inside construction
  primes' solicitations.
* Adjacent OT/ICS clauses (UFC 4-010-06, NIST SP 800-82, DoDI 8500.01,
  FRCS, UMCS, SCADA security, OT cyber, PIT cyber, eMASS+ICS, Civil Works+PLC).
* Clearance requirements (TS/SCI, SCIF, Polygraph, FCL+Top Secret).
* Role triggers (CSA, ISSM, ISSE, RMF Validator, 3PAO).

The detector is a pure function with no DB or LLM calls — fast to unit
test, and called inline by the scoring worker after attachment text lands.

Pattern dictionaries are passed in (read from the tenant's
high_moat_scoring config block) so re-tuning vocabulary doesn't need a
deploy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

TopClearance = Literal["TS_SCI", "TS", "S", "NONE"]


@dataclass(frozen=True)
class ClauseFindings:
    """Structured detection result for a single opportunity."""

    clause_hits: list[str] = field(default_factory=list)
    clearance_hits: list[str] = field(default_factory=list)
    role_hits: list[str] = field(default_factory=list)
    top_clearance: TopClearance = "NONE"
    has_ufgs_25_exact: bool = False  # 25 05 11 or 25 08 11
    has_ufgs_25_division: bool = False  # other UFGS 25 reference

    @property
    def has_ufgs_25_clause(self) -> bool:
        return self.has_ufgs_25_exact or self.has_ufgs_25_division


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    out: list[re.Pattern[str]] = []
    for p in patterns:
        # Treat the configured patterns as literal phrases (with whitespace
        # tolerance), not regex syntax — UFGS clause numbers and similar contain
        # characters that would otherwise need escaping. Word-boundary anchoring
        # keeps "TS" out of "TSA" and "FCL" out of "FCLU".
        escaped = re.escape(p.strip())
        # Allow flexible internal whitespace (\s+) so "TS/SCI" matches "TS / SCI"
        # and "25 05 11" matches "25  05  11" (double-spaced PDFs).
        flexible = re.sub(r"\\\s+", r"\\s+", escaped)
        anchored = rf"(?<![A-Za-z0-9]){flexible}(?![A-Za-z0-9])"
        out.append(re.compile(anchored, re.IGNORECASE))
    return out


def _any_match(text: str, compiled: list[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in compiled)


def detect(
    *,
    title: str | None,
    description_text: str | None = None,
    attachment_text: str | None = None,
    clause_patterns: dict[str, list[str]],
    clearance_patterns: dict[str, list[str]],
    role_patterns: dict[str, list[str]],
) -> ClauseFindings:
    """Return structured findings for the union of the supplied texts."""
    blob = " \n ".join(filter(None, [title, description_text, attachment_text]))
    if not blob.strip():
        return ClauseFindings()

    clause_compiled = {k: _compile(v) for k, v in clause_patterns.items()}
    clearance_compiled = {k: _compile(v) for k, v in clearance_patterns.items()}
    role_compiled = {k: _compile(v) for k, v in role_patterns.items()}

    clause_hits: list[str] = []
    for family, compiled in clause_compiled.items():
        if not _any_match(blob, compiled):
            continue
        if family == "emass_ics":
            # eMASS by itself isn't an OT/ICS signal — only counts when paired
            # with an industrial / control-systems mention in the same blob.
            if not re.search(
                r"\b(ICS|industrial(?:\s+control)?|control\s+systems?)\b",
                blob,
                re.IGNORECASE,
            ):
                continue
        if family == "civil_works_plc":
            # "Civil Works" alone is too broad (it's a USACE construction
            # category). Only counts when paired with PLC / cyber / control.
            if not re.search(
                r"\b(PLC|cyber(?:security)?|control\s+system|SCADA)\b",
                blob,
                re.IGNORECASE,
            ):
                continue
        clause_hits.append(family)

    clearance_hits = [
        family
        for family, compiled in clearance_compiled.items()
        if _any_match(blob, compiled)
    ]
    role_hits = [
        family
        for family, compiled in role_compiled.items()
        if _any_match(blob, compiled)
    ]

    has_exact = ("ufgs_25_05_11" in clause_hits) or ("ufgs_25_08_11" in clause_hits)
    has_division = "ufgs_25_other" in clause_hits

    if "ts_sci" in clearance_hits:
        top: TopClearance = "TS_SCI"
    elif "fcl_ts" in clearance_hits or "polygraph" in clearance_hits:
        # An FCL-at-Top-Secret tier or polygraph requirement implies TS
        # personnel even when "TS/SCI" isn't spelled out.
        top = "TS"
    elif "secret_only" in clearance_hits:
        top = "S"
    else:
        top = "NONE"

    return ClauseFindings(
        clause_hits=clause_hits,
        clearance_hits=clearance_hits,
        role_hits=role_hits,
        top_clearance=top,
        has_ufgs_25_exact=has_exact,
        has_ufgs_25_division=has_division,
    )
