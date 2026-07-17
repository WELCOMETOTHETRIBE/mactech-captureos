"""Loader for the versioned capture knowledge pack.

The pack is a directory of YAML family files under ``config/capture_knowledge/``.
Each file declares a ``family`` and a ``version`` and carries either a list of
``concepts`` (signal vocabulary) and/or structured retrieval blocks
(``query_families``, ``notice_types``, ``agencies``, ``playbooks`` …).

This module is deliberately free of any ``cyber_scope`` imports so it can be a
leaf dependency: ``cyber_scope.dictionary`` and the query-family builder import
*from here*, never the reverse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# repo_root/packages/intelligence/src/mactech_intelligence/knowledge/pack.py
_REPO_ROOT = Path(__file__).resolve().parents[5]
_PACK_DIR = _REPO_ROOT / "config" / "capture_knowledge"

# The evidence categories the *legacy* cyber_scope detector understands
# (mirrors ``DetectedCategories`` in cyber_scope/schemas.py). Only concepts
# tagged with one of these are projected into the legacy dictionary by
# ``cyber_scope.dictionary``. New signal families (direct_cyber, facility_
# adjacency, acquisition_context, barrier, training …) carry different
# categories and are switched on by the generalized detector in Slice 3.
LEGACY_EVIDENCE_CATEGORIES: frozenset[str] = frozenset(
    {
        "ufc_frcs",
        "rmf_ato_emass",
        "nist_cnssi_fips",
        "ot_ics_scada_pit",
        "branch_specific",
        "contract_location_triggers",
        "far_dfars_cmmc",
    }
)


@dataclass(frozen=True)
class Concept:
    """One capture concept. Every field the overhaul brief requires a concept
    to *support* is present; new-family concepts may leave the optional ones
    empty."""

    id: str
    family: str
    canonical_name: str
    evidence_category: str | None
    normalized_term: str
    aliases: tuple[str, ...] = ()
    abbreviations: tuple[str, ...] = ()
    exact_phrases: tuple[str, ...] = ()
    regex: str | None = None
    related_concepts: tuple[str, ...] = ()
    positive_weight: int = 0
    negative_weight: int = 0
    disqualifier: bool = False
    gate_code: str | None = None
    severity: str | None = None  # "hard" | "soft" — for disqualifier concepts
    ufgs: str | None = None
    ufgs_tier: int | None = None
    source_ref: str | None = None
    effective_date: date | None = None
    enabled: bool = True

    @property
    def match_patterns(self) -> tuple[str, ...]:
        """Literal patterns used by the matcher when no regex is set — the
        canonical name plus every alias/abbreviation/exact phrase, deduped and
        order-preserving."""
        seen: dict[str, None] = {}
        for p in (self.canonical_name, *self.aliases, *self.abbreviations, *self.exact_phrases):
            if p and p not in seen:
                seen[p] = None
        return tuple(seen)


@dataclass(frozen=True)
class KnowledgePack:
    versions: dict[str, str]
    concepts: tuple[Concept, ...]
    # Non-concept structured blocks, keyed by family then block name.
    blocks: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def pack_version(self) -> str:
        return ";".join(f"{fam}={ver}" for fam, ver in sorted(self.versions.items()))

    def by_family(self, family: str) -> tuple[Concept, ...]:
        return tuple(c for c in self.concepts if c.family == family)

    def by_evidence_category(self, category: str) -> tuple[Concept, ...]:
        return tuple(c for c in self.concepts if c.evidence_category == category)

    def by_id(self, concept_id: str) -> Concept | None:
        for c in self.concepts:
            if c.id == concept_id:
                return c
        return None

    @property
    def disqualifiers(self) -> tuple[Concept, ...]:
        return tuple(c for c in self.concepts if c.disqualifier)

    def block(self, family: str, name: str, default: Any = None) -> Any:
        return self.blocks.get(family, {}).get(name, default)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


# Top-level keys that are metadata, not structured retrieval blocks.
_META_KEYS = {"family", "version", "effective_date", "concepts"}


def _load_dir(pack_dir: Path, *, as_of: date) -> KnowledgePack:
    versions: dict[str, str] = {}
    concepts: list[Concept] = []
    blocks: dict[str, dict[str, Any]] = {}

    if not pack_dir.is_dir():
        return KnowledgePack(versions={}, concepts=(), blocks={})

    for yaml_path in sorted(pack_dir.glob("*.yml")):
        raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        family = str(raw.get("family") or yaml_path.stem)
        versions[family] = str(raw.get("version", "0"))
        family_effective = _parse_date(raw.get("effective_date"))

        for c in raw.get("concepts", []) or []:
            if not c.get("enabled", True):
                continue
            eff = _parse_date(c.get("effective_date")) or family_effective
            if eff is not None and eff > as_of:
                continue
            canonical = str(c["canonical_name"])
            concepts.append(
                Concept(
                    id=str(c["id"]),
                    family=family,
                    canonical_name=canonical,
                    evidence_category=c.get("evidence_category"),
                    normalized_term=str(c.get("normalized_term") or canonical),
                    aliases=_as_tuple(c.get("aliases")),
                    abbreviations=_as_tuple(c.get("abbreviations")),
                    exact_phrases=_as_tuple(c.get("exact_phrases")),
                    regex=c.get("regex"),
                    related_concepts=_as_tuple(c.get("related_concepts")),
                    positive_weight=int(c.get("positive_weight", 0)),
                    negative_weight=int(c.get("negative_weight", 0)),
                    disqualifier=bool(c.get("disqualifier", False)),
                    gate_code=c.get("gate_code"),
                    severity=c.get("severity"),
                    ufgs=c.get("ufgs"),
                    ufgs_tier=(int(c["ufgs_tier"]) if c.get("ufgs_tier") is not None else None),
                    source_ref=c.get("source_ref"),
                    effective_date=eff,
                    enabled=True,
                )
            )

        extra = {k: v for k, v in raw.items() if k not in _META_KEYS}
        if extra:
            blocks[family] = extra

    return KnowledgePack(versions=versions, concepts=tuple(concepts), blocks=blocks)


@lru_cache(maxsize=1)
def load_pack(pack_dir: Path | None = None) -> KnowledgePack:
    """Load and cache the knowledge pack. ``effective_date`` filtering uses the
    load-time date; the cache lives for the process lifetime, which is the same
    contract the existing ``cyber_scope`` loaders use."""
    return _load_dir(pack_dir or _PACK_DIR, as_of=date.today())


def pack_version(pack_dir: Path | None = None) -> str:
    return load_pack(pack_dir).pack_version
