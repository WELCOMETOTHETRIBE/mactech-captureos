"""Route a bid invite to the founder whose pillar owns the scope.

BuildingConnected invites carry no NAICS code, so routing keys off the
bid package / project text instead: deterministic keyword buckets per
founder pillar (same assignments data/naics_matrix.json encodes for
SAM opportunities). A miss returns None — an unassigned pursuit beats
a confidently wrong one.

Also home to the project group key: the stable identity that ties an
invite + its reminders + due-date changes to one solicitation, shared
by the webhook (auto-linking), the pursue endpoint (opportunity
source_id), and mirrored in the web app's grouping
(apps/web/lib/bid-invite-view.ts — keep normalization in sync).
"""

from __future__ import annotations

import re

# Ordered: first bucket whose keywords hit wins. Security outranks
# infrastructure so "Security Upgrades: Data & Telecom" routes to the
# security pillar, matching how the NAICS matrix biases 541512/541519.
_PILLAR_KEYWORDS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "patrick-caruso",
        (
            "security",
            "erces",
            "fire alarm",
            "fire protection",
            "surveillance",
            "access control",
            "cctv",
            "cyber",
            "cui",
        ),
        "security / low-voltage scope",
    ),
    (
        "brian-macdonald",
        (
            "testing",
            "materials",
            "inspection",
            "commissioning",
            "quality",
            "metrology",
            "calibration",
            "lab",
        ),
        "testing / quality scope",
    ),
    (
        "james-adams",
        (
            "data",
            "telecom",
            "network",
            "communications",
            "building management",
            "bms",
            "automation",
            "mechanical",
            "electrical",
            "infrastructure",
        ),
        "infrastructure / systems scope",
    ),
    (
        "john-milso",
        ("legal", "contract review", "compliance review"),
        "contracts / governance scope",
    ),
)


def suggest_founder(*text_fields: str | None) -> tuple[str, str] | None:
    """Return (founder_slug, reason) for the first pillar whose keywords
    appear in any of the given fields, or None when nothing matches."""
    probe = " ".join(f.lower() for f in text_fields if f)
    if not probe:
        return None
    for slug, keywords, reason in _PILLAR_KEYWORDS:
        for kw in keywords:
            if kw in probe:
                return slug, f"{reason} (“{kw}”)"
    return None


def project_group_key(project_name: str | None, subject: str) -> str:
    """Normalize a project identity so every email about one solicitation
    lands on the same key ("Kings Bay Project" == "Kings Bay")."""
    raw = project_name or subject
    return (
        re.sub(
            r"[^a-z0-9]+",
            " ",
            re.sub(r"\bproject\b", "", raw.lower()),
        ).strip()
        or raw.lower()
    )
