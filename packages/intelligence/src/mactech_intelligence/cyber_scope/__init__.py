"""Cyber Scope Contract Parser — deterministic FRCS/OT/UFGS detection."""

from mactech_intelligence.cyber_scope.analyze import analyze_cyber_scope
from mactech_intelligence.cyber_scope.schemas import (
    CyberScopeAnalysis,
    DetectionResult,
    SuggestedAction,
)
from mactech_intelligence.cyber_scope.scorer import PARSER_VERSION
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource

__all__ = [
    "CyberScopeAnalysis",
    "CyberScopeTextSource",
    "DetectionResult",
    "PARSER_VERSION",
    "SuggestedAction",
    "analyze_cyber_scope",
]
