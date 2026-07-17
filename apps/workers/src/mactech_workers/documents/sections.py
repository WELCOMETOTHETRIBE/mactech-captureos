"""Section / page provenance.

Turns extracted text (per-page for PDFs, single-blob otherwise) into ordered
``Section`` records carrying page number, a detected heading, and character
offsets into the concatenated document text. These offsets are the stable
anchors the detector cites as evidence (page N, "Section 25 05 11", chars a-b).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Headings worth anchoring on: FAR sections, spec divisions, UFGS numbers.
_HEADING_PATTERNS = [
    # Spec-number section headings ("SECTION 25 05 11 …") — check before the
    # generic "SECTION <letter>" form so numbered specs win.
    re.compile(r"^\s*(SECTION\s+\d\d\s?\d\d\s?\d\d(?:\.\d\d)?[^\n]{0,80})", re.I | re.M),
    re.compile(r"^\s*(SECTION\s+[A-M]\b[^\n]{0,80})", re.I | re.M),
    re.compile(r"^\s*(DIVISION\s+\d{1,2}\b[^\n]{0,80})", re.I | re.M),
    re.compile(r"^\s*(UFGS\s+\d\d\s?\d\d\s?\d\d[^\n]{0,80})", re.I | re.M),
    re.compile(r"^\s*(\d\d\s\d\d\s\d\d(?:\.\d\d)?(?:\s\d\d)?\s+[A-Z][^\n]{0,80})", re.M),
    re.compile(r"^\s*(PART\s+\d\b[^\n]{0,80})", re.I | re.M),
]

_JOIN = "\n\n"


@dataclass(frozen=True)
class Section:
    ordinal: int
    page_number: int | None
    section_heading: str | None
    section_path: str | None
    char_start: int
    char_end: int
    text: str


def _detect_heading(text: str) -> str | None:
    for pat in _HEADING_PATTERNS:
        m = pat.search(text)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()[:255]
    return None


def build_sections(pages: list[str], *, combined_text: str | None = None) -> list[Section]:
    """One section per page (PDF) or one section for the whole doc. Character
    offsets are into the concatenated text (``_JOIN``-separated), which must
    match how the caller stores the document body so evidence offsets line up."""
    if not pages:
        return []

    sections: list[Section] = []
    cursor = 0
    for i, page_text in enumerate(pages):
        start = cursor
        end = start + len(page_text)
        sections.append(
            Section(
                ordinal=i,
                page_number=(i + 1) if len(pages) > 1 else None,
                section_heading=_detect_heading(page_text),
                section_path=None,
                char_start=start,
                char_end=end,
                text=page_text,
            )
        )
        # Advance cursor past this page plus the join separator the caller uses.
        cursor = end + len(_JOIN)
    return sections


def combined_text(pages: list[str]) -> str:
    return _JOIN.join(pages)
