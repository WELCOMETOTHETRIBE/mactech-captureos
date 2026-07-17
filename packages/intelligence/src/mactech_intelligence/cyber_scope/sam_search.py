"""Build SAM.gov search jobs for cyber-scope saved searches."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Predefined title queries for `sam_query_group` on saved searches.
# SAM `title` param is a direct lookup — keep terms short and specific.
SAM_QUERY_GROUPS: dict[str, list[str]] = {
    "ufgs_tier1": [
        "25 05 11",
        "25 08 11",
        "25 10 10",
        "25 08 10",
    ],
    "ufgs_shortlist": [
        "25 05 11",
        "25 08 11.00 20",
        "23 09 23.02",
        "28 10 05",
        "27 05 29.00 10",
        "26 37 13",
        "40 60 00",
    ],
    "ufc_frcs_rmf": [
        "UFC 4-010-06",
        "FRCS",
        "DoDI 8510.01",
        "RMF",
    ],
    "hidden_construction": [
        "HVAC controls",
        "building automation",
        "BACnet",
        "UMCS",
    ],
    "ot_ics": [
        "SCADA",
        "UMCS",
        "Operational Technology",
    ],
}

# Terms from generate_search_queries that are too long for SAM title param.
_TITLE_MAX_LEN = 80


def all_query_groups() -> dict[str, list[str]]:
    """Static groups plus the knowledge-pack query families (Slice 1).

    Static groups keep priority on any key collision. Falls back to the static
    dict alone if the pack is unavailable, so this stays import-safe.
    """
    merged = dict(SAM_QUERY_GROUPS)
    try:
        from mactech_intelligence.knowledge.query_families import query_family_groups

        for key, titles in query_family_groups().items():
            merged.setdefault(key, titles)
    except Exception:  # pragma: no cover - pack optional; never break retrieval
        pass
    return merged


@dataclass(frozen=True)
class SamCyberSearchJob:
    """One SAM API search unit (rate-limit budget = 1+ pages per job)."""

    saved_search_id: str
    saved_search_name: str
    tenant_id: str
    naics_code: str | None
    title_query: str | None
    keywords: tuple[str, ...]
    state_key: str
    max_pages: int = 2
    page_size: int = 100


def is_cyber_scope_saved_search(filters: dict[str, Any]) -> bool:
    if filters.get("cyber_scope_search"):
        return True
    if (filters.get("score_field") or "").strip() == "cyber_scope_score":
        return True
    name = str(filters.get("_name") or "")
    if "CYBER SCOPE" in name.upper() or "MACTECH SHORTLIST" in name.upper():
        return True
    if "HIDDEN CONSTRUCTION CYBER" in name.upper():
        return True
    return False


def search_keywords_from_filters(filters: dict[str, Any]) -> list[str]:
    """Keywords used for client-side title/solicitation matching after NAICS pull."""
    raw = [k for k in (filters.get("keywords") or []) if isinstance(k, str) and k.strip()]
    cap = set(filters.get("capability_keywords") or [])
    return [k for k in raw if k not in cap]


def title_queries_for_filters(filters: dict[str, Any]) -> list[str]:
    """Explicit or grouped SAM `title` lookups."""
    explicit = [
        t.strip()
        for t in (filters.get("sam_title_queries") or [])
        if isinstance(t, str) and t.strip()
    ]
    if explicit:
        return [t[:_TITLE_MAX_LEN] for t in explicit]

    registry = all_query_groups()

    group = (filters.get("sam_query_group") or "").strip()
    if group and group in registry:
        return [t[:_TITLE_MAX_LEN] for t in registry[group]]

    groups = filters.get("sam_query_groups") or []
    out: list[str] = []
    for g in groups:
        if isinstance(g, str) and g in registry:
            out.extend(registry[g])
    return [t[:_TITLE_MAX_LEN] for t in dict.fromkeys(out)]


def build_sam_cyber_jobs(
    *,
    saved_search_id: str,
    saved_search_name: str,
    tenant_id: str,
    filters: dict[str, Any],
) -> list[SamCyberSearchJob]:
    """Expand a cyber saved search into bounded SAM API jobs."""
    if not is_cyber_scope_saved_search(filters):
        return []

    keywords = tuple(search_keywords_from_filters(filters))
    naics_codes = [n for n in (filters.get("naics") or []) if isinstance(n, str) and n.strip()]
    title_queries = title_queries_for_filters(filters)
    jobs: list[SamCyberSearchJob] = []

    for naics in naics_codes:
        jobs.append(
            SamCyberSearchJob(
                saved_search_id=saved_search_id,
                saved_search_name=saved_search_name,
                tenant_id=tenant_id,
                naics_code=naics,
                title_query=None,
                keywords=keywords,
                state_key=f"cyber_scope_sam:{saved_search_id}:naics:{naics}",
            )
        )

    for title in title_queries:
        # Title search is cross-NAICS; attach first NAICS as optional narrow if single code.
        narrow = naics_codes[0] if len(naics_codes) == 1 else None
        safe_title = re.sub(r"[^\w\s\.\-/]", " ", title).strip()[:_TITLE_MAX_LEN]
        if not safe_title:
            continue
        jobs.append(
            SamCyberSearchJob(
                saved_search_id=saved_search_id,
                saved_search_name=saved_search_name,
                tenant_id=tenant_id,
                naics_code=narrow,
                title_query=safe_title,
                keywords=keywords,
                state_key=f"cyber_scope_sam:{saved_search_id}:title:{safe_title[:40]}",
                max_pages=1,
            )
        )

    return jobs


def record_matches_keywords(
    *,
    title: str | None,
    solicitation_number: str | None,
    keywords: tuple[str, ...],
) -> bool:
    if not keywords:
        return True
    blob = f"{title or ''} {solicitation_number or ''}".upper()
    return any(k.upper() in blob for k in keywords)


def default_query_groups_for_seed() -> dict[str, str]:
    """Map seed saved search names to query groups (documentation helper)."""
    return {
        "Patrick — UFGS MacTech Shortlist": "ufgs_shortlist",
        "Patrick — Hidden Construction Cyber": "hidden_construction",
    }
