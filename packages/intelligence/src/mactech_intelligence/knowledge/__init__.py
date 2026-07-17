"""Versioned capture knowledge pack.

The pack lives in ``config/capture_knowledge/*.yml`` and holds every capture
concept — signal vocabulary, acquisition/query signals, agency offices,
disqualifiers, and pursuit playbooks — as data, so it can be replaced without
touching Python. See ``docs/CAPTURE_RULEBOOK.md`` for the taxonomy.
"""

from mactech_intelligence.knowledge.pack import (
    LEGACY_EVIDENCE_CATEGORIES,
    Concept,
    KnowledgePack,
    load_pack,
    pack_version,
)

__all__ = [
    "LEGACY_EVIDENCE_CATEGORIES",
    "Concept",
    "KnowledgePack",
    "load_pack",
    "pack_version",
]
