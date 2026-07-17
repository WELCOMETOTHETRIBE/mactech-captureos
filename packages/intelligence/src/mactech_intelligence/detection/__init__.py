"""Multi-family signal detection (Slice 3).

Generalizes the FRCS-only cyber_scope detector into a pack-driven detector that
scans across every enabled knowledge-pack family — direct cyber, FRCS/OT,
facility adjacency, construction/acquisition context, and barriers — retaining
page/section evidence. It is *additive*: the legacy cyber_scope scorer is
untouched (it still reads only the legacy-category concepts), so this feeds the
Slice 4 decision engine without disturbing existing scores.
"""

from mactech_intelligence.detection.identifiers import (
    IdentifierHit,
    canonical_dfars,
    canonical_ufgs,
    find_identifiers,
)
from mactech_intelligence.detection.signals import (
    SignalHit,
    SignalReport,
    detect_signals,
)

__all__ = [
    "IdentifierHit",
    "SignalHit",
    "SignalReport",
    "canonical_dfars",
    "canonical_ufgs",
    "detect_signals",
    "find_identifiers",
]
