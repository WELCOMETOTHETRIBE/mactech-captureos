"""The five SAM.gov query families (recall-first retrieval).

Built from ``config/capture_knowledge/acquisition_signals.yml``. Each family
exposes broad ``naics`` pulls (no cyber language required at the API) and short
``title_queries`` (direct SAM ``title`` lookups). ``cyber_scope.sam_search``
merges the per-family title groups into ``SAM_QUERY_GROUPS`` so existing
saved-search plumbing resolves them with no structural change.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from mactech_intelligence.knowledge.pack import load_pack

_FAMILY = "acquisition_signals"


@dataclass(frozen=True)
class QueryFamily:
    key: str
    label: str
    pipeline: str  # "A" | "B" | "AB"
    naics: tuple[str, ...]
    title_queries: tuple[str, ...]
    enabled: bool = True


@lru_cache(maxsize=1)
def query_families() -> tuple[QueryFamily, ...]:
    raw = load_pack().block(_FAMILY, "query_families", []) or []
    families: list[QueryFamily] = []
    for f in raw:
        if not f.get("enabled", True):
            continue
        families.append(
            QueryFamily(
                key=str(f["key"]),
                label=str(f.get("label", f["key"])),
                pipeline=str(f.get("pipeline", "AB")),
                naics=tuple(str(n) for n in f.get("naics", []) if str(n).strip()),
                title_queries=tuple(
                    str(t) for t in f.get("title_queries", []) if str(t).strip()
                ),
            )
        )
    return tuple(families)


def query_family_groups() -> dict[str, list[str]]:
    """family key -> title_queries, for merge into SAM_QUERY_GROUPS."""
    return {f.key: list(f.title_queries) for f in query_families() if f.title_queries}


def family_naics() -> dict[str, list[str]]:
    """family key -> broad NAICS pull list."""
    return {f.key: list(f.naics) for f in query_families()}


def all_family_naics() -> tuple[str, ...]:
    """Deduped union of every enabled family's NAICS — the recall-first
    candidate NAICS universe."""
    seen: dict[str, None] = {}
    for f in query_families():
        for n in f.naics:
            seen.setdefault(n, None)
    return tuple(seen)


def notice_types(bucket: str) -> tuple[str, ...]:
    types = load_pack().block(_FAMILY, "notice_types", {}) or {}
    return tuple(types.get(bucket, []))
