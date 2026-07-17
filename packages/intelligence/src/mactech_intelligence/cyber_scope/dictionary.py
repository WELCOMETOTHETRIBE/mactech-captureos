"""Load the general cyber-scope dictionary.

Slice 1 of the capture-engine overhaul moved the dictionary into the versioned
knowledge pack (``config/capture_knowledge/*.yml``). This module is now a thin
compatibility adapter: it projects the pack's LEGACY-category concepts into the
same ``DictionaryTerm`` tuple the matcher has always consumed, so
``matcher.run_dictionary_matching`` and every cyber_scope test keep working
unchanged. If the pack is missing (or yields no legacy concepts) it falls back
to the original ``data/cyber_scope_dictionary.yml`` — a zero-downtime cutover.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from mactech_intelligence.knowledge.pack import LEGACY_EVIDENCE_CATEGORIES, load_pack

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DICT_YAML = _REPO_ROOT / "data" / "cyber_scope_dictionary.yml"


@dataclass(frozen=True)
class DictionaryTerm:
    category: str
    term: str
    normalized_term: str
    weight: int
    aliases: tuple[str, ...]
    regex: str | None = None


def _dedupe(items: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(i for i in items if i))


def _from_pack() -> tuple[DictionaryTerm, ...]:
    """Project the pack's legacy-category concepts into DictionaryTerms.

    Only concepts whose ``evidence_category`` is one the legacy detector
    understands are included; new signal families (barrier, facility_adjacency,
    …) are switched on by the generalized detector in Slice 3.
    """
    pack = load_pack()
    terms: list[DictionaryTerm] = []
    for c in pack.concepts:
        if c.evidence_category not in LEGACY_EVIDENCE_CATEGORIES:
            continue
        terms.append(
            DictionaryTerm(
                category=c.evidence_category,
                term=c.canonical_name,
                normalized_term=c.normalized_term,
                weight=c.positive_weight,
                aliases=_dedupe([*c.aliases, *c.abbreviations, *c.exact_phrases]),
                regex=c.regex,
            )
        )
    return tuple(terms)


def _from_yaml(yaml_path: Path) -> tuple[DictionaryTerm, ...]:
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    terms = []
    for t in raw.get("terms", []):
        terms.append(
            DictionaryTerm(
                category=t["category"],
                term=t["term"],
                normalized_term=t.get("normalized_term", t["term"]),
                weight=int(t.get("weight", 10)),
                aliases=tuple(t.get("aliases", [])),
                regex=t.get("regex"),
            )
        )
    return tuple(terms)


@lru_cache(maxsize=2)
def load_dictionary(path: Path | None = None) -> tuple[DictionaryTerm, ...]:
    # Explicit path keeps the original file-based behavior (used by tooling and
    # the parity test's reference loader).
    if path is not None:
        return _from_yaml(path)
    from_pack = _from_pack()
    if from_pack:
        return from_pack
    return _from_yaml(_DICT_YAML)


@lru_cache(maxsize=2)
def load_construction_signals(path: Path | None = None) -> tuple[str, ...]:
    if path is not None:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return tuple(raw.get("construction_signals", []))
    signals = load_pack().block("construction_systems", "construction_signals", [])
    if signals:
        return tuple(signals)
    raw = yaml.safe_load(_DICT_YAML.read_text(encoding="utf-8"))
    return tuple(raw.get("construction_signals", []))
