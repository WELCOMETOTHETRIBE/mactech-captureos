"""Identifier normalization for UFGS spec numbers and DFARS clauses.

Federal documents write the same identifier a dozen ways. These helpers collapse
every variant to one canonical form so the detector and the knowledge pack agree
on identity:

    25 05 11 / 25-05-11 / 250511 / UFGS 25 05 11 / Section 25 05 11  -> "25 05 11"
    252.204-7012 / 252 204 7012 / 2522047012 / DFARS 252.204-7012    -> "252.204-7012"

Compact all-digit forms (250511, 2522047012) are only accepted when preceded by a
context word (UFGS/Section/Division for specs; DFARS/FAR/clause for clauses) so
bare numbers in prices or dates don't produce false hits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# UFGS section: DD DD DD with optional .DD and optional trailing " DD" group,
# separators = space / ASCII hyphen / any unicode dash (U+2010..U+2015) / none.
# Written with escapes (not literal dashes) to stay unambiguous for linters.
# The class fragment U+2010..U+2015 is a RANGE covering hyphen, non-breaking
# hyphen, figure dash, en dash, em dash, horizontal bar; trailing "-" is literal
# ASCII hyphen-minus.
_DASH = "\u2010-\u2015-"
_SEP = rf"[\s{_DASH}]?"
_UFGS_CORE = rf"(\d{{2}}){_SEP}(\d{{2}}){_SEP}(\d{{2}})(?:\.(\d{{2}}))?(?:{_SEP}(\d{{2}}))?"
_UFGS_PREFIXED = re.compile(rf"(?:UFGS|Section|Sec\.?|Division)\s+{_UFGS_CORE}", re.I)
# Bare form requires visible separators (avoids matching random 6-digit numbers).
_UFGS_SPACED = re.compile(
    rf"(?<![\d.])(\d{{2}})[\s{_DASH}](\d{{2}})[\s{_DASH}](\d{{2}})(?:\.(\d{{2}}))?(?![\d])"
)

# DFARS/FAR clause: 3-digit part, dot, 3-digit subpart, sep, 4-digit clause.
_CLAUSE_CORE = rf"(\d{{3}})\.?{_SEP}(\d{{3}})[\s{_DASH}.]?(\d{{4}})"
_CLAUSE_PREFIXED = re.compile(rf"(?:DFARS|FAR|clause)\s+{_CLAUSE_CORE}", re.I)
_CLAUSE_DOTTED = re.compile(rf"(?<!\d)(\d{{3}})\.(\d{{3}})[\s{_DASH}.](\d{{4}})(?!\d)")


@dataclass(frozen=True)
class IdentifierHit:
    kind: str  # "ufgs" | "dfars"
    canonical: str
    raw: str
    start: int
    end: int


def canonical_ufgs(*parts: str | None) -> str:
    """Assemble canonical 'DD DD DD[.DD][ DD]' from captured groups or a raw
    string. Accepts either the 3-5 group tuple or a single raw token."""
    if len(parts) == 1:
        raw = re.sub(r"(?:UFGS|Section|Sec\.?|Division)\s+", "", parts[0] or "", flags=re.I)
        digits_groups = re.findall(r"\d+", raw)
        parts = tuple(digits_groups)  # type: ignore[assignment]
    g = [p for p in parts if p]
    if len(g) < 3:
        return " ".join(g)
    base = f"{g[0]} {g[1]} {g[2]}"
    # A 2-digit 4th group after the triple is a decimal minor (".DD"); a further
    # 2-digit group is a trailing " DD".
    rest = g[3:]
    if rest:
        base += "." + rest[0]
        if len(rest) > 1:
            base += " " + rest[1]
    return base


def canonical_dfars(*parts: str | None) -> str:
    if len(parts) == 1:
        digits = re.findall(r"\d+", parts[0] or "")
        parts = tuple(digits)  # type: ignore[assignment]
    g = [p for p in parts if p]
    if len(g) >= 3:
        return f"{g[0]}.{g[1]}-{g[2]}"
    return "".join(g)


def find_identifiers(text: str) -> list[IdentifierHit]:
    """Return normalized UFGS + DFARS identifier hits, de-overlapped."""
    hits: list[IdentifierHit] = []
    seen_spans: list[tuple[int, int]] = []

    def _overlaps(s: int, e: int) -> bool:
        return any(not (e <= a or s >= b) for a, b in seen_spans)

    def _collect(pattern: re.Pattern[str], kind: str, canon) -> None:
        for m in pattern.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e):
                continue
            groups = [g for g in m.groups() if g]
            canonical = canon(*groups) if groups else canon(m.group(0))
            hits.append(IdentifierHit(kind=kind, canonical=canonical, raw=m.group(0), start=s, end=e))
            seen_spans.append((s, e))

    # Prefixed forms first (highest confidence), then bare separated forms.
    _collect(_UFGS_PREFIXED, "ufgs", canonical_ufgs)
    _collect(_CLAUSE_PREFIXED, "dfars", canonical_dfars)
    _collect(_UFGS_SPACED, "ufgs", canonical_ufgs)
    _collect(_CLAUSE_DOTTED, "dfars", canonical_dfars)

    hits.sort(key=lambda h: h.start)
    return hits


def normalize_identifier(kind: str, raw: str) -> str:
    if kind == "ufgs":
        return canonical_ufgs(raw)
    if kind == "dfars":
        return canonical_dfars(raw)
    return raw.strip()
