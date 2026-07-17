"""Dictionary and regex matching for cyber scope terms."""

from __future__ import annotations

from mactech_intelligence.cyber_scope.dictionary import DictionaryTerm, load_dictionary
from mactech_intelligence.cyber_scope.regex_utils import (
    compile_literal_patterns,
    compile_regex_pattern,
    surrounding_text,
)
from mactech_intelligence.cyber_scope.schemas import DetectionResult


def _match_term(
    text: str, term: DictionaryTerm, match_type: str = "EXACT"
) -> list[DetectionResult]:
    hits: list[DetectionResult] = []
    patterns = [term.term, *term.aliases]
    if term.regex:
        regex = term.regex.strip("/")
        if regex.endswith("/i"):
            regex = regex[:-2]
        compiled = [compile_regex_pattern(regex)]
        mt: str = "REGEX"
    else:
        compiled = compile_literal_patterns(patterns)
        mt = match_type

    for pat in compiled:
        for m in pat.finditer(text):
            hits.append(
                DetectionResult(
                    term=term.term,
                    normalized_term=term.normalized_term,
                    category=term.category,
                    confidence=1.0,
                    weight=term.weight,
                    match_type=mt,  # type: ignore[arg-type]
                    surrounding_text=surrounding_text(text, m.start(), m.end()),
                )
            )
            break
        if hits:
            break
    return hits


def run_dictionary_matching(text: str) -> dict[str, list[DetectionResult]]:
    by_category: dict[str, list[DetectionResult]] = {}
    for term in load_dictionary():
        found = _match_term(text, term)
        if not found:
            continue
        by_category.setdefault(term.category, []).extend(found)
    return by_category


def run_regex_matching(text: str) -> list[DetectionResult]:
    """Alias — regex terms are handled inside run_dictionary_matching."""
    all_hits: list[DetectionResult] = []
    for cat_hits in run_dictionary_matching(text).values():
        all_hits.extend(cat_hits)
    return all_hits
