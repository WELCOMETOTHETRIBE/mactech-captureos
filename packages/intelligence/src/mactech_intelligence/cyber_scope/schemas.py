"""Pydantic schemas for Cyber Scope analysis."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CyberLikelihood = Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
PursuitModel = Literal[
    "NO_ACTION",
    "WATCHLIST",
    "PRIME_PURSUE",
    "SUBCONTRACTOR_PURSUE",
    "CYBER_SUPPORT_ONLY",
    "FRCS_OT_SPECIALIST",
    "CMMC_COMPLIANCE_SUPPORT",
    "CLARIFICATION_REQUIRED",
]
SourceType = Literal[
    "SAM_INGEST",
    "SAM_SEARCH",
    "PASTED_TEXT",
    "UPLOAD",
    "FPDS_SEARCH",
    "OTHER",
]
MatchType = Literal["EXACT", "FUZZY", "REGEX", "SEMANTIC"]
ScanPass = Literal["description_only", "with_attachments"]


class DetectionResult(BaseModel):
    term: str
    normalized_term: str
    category: str
    confidence: float = 1.0
    weight: int = 0
    match_type: MatchType = "EXACT"
    surrounding_text: str = ""
    page_number: int | None = None
    section_heading: str | None = None
    document_name: str | None = None
    ufgs: str | None = None
    ufgs_tier: int | None = None


class SuggestedAction(BaseModel):
    action_type: str
    title: str
    rationale: str
    priority: Literal["LOW", "MEDIUM", "HIGH", "URGENT"] = "MEDIUM"


class DetectedCategories(BaseModel):
    ufc_frcs: list[DetectionResult] = Field(default_factory=list)
    ufgs: list[DetectionResult] = Field(default_factory=list)
    ufgs_by_tier: dict[str, list[DetectionResult]] = Field(default_factory=dict)
    rmf_ato_emass: list[DetectionResult] = Field(default_factory=list)
    nist_cnssi_fips: list[DetectionResult] = Field(default_factory=list)
    ot_ics_scada_pit: list[DetectionResult] = Field(default_factory=list)
    branch_specific: list[DetectionResult] = Field(default_factory=list)
    contract_location_triggers: list[DetectionResult] = Field(default_factory=list)
    far_dfars_cmmc: list[DetectionResult] = Field(default_factory=list)


class CyberScopeAnalysis(BaseModel):
    overall_cyber_likelihood: CyberLikelihood
    recommended_pursuit_model: PursuitModel
    score: int
    detected_categories: DetectedCategories
    top_signals: list[DetectionResult] = Field(default_factory=list)
    hidden_scope_indicators: list[DetectionResult] = Field(default_factory=list)
    missing_but_likely_requirements: list[str] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    evidence_snippets: list[DetectionResult] = Field(default_factory=list)
    ufgs_center_of_gravity: bool = False
    ufgs_tier_1_hit: bool = False
    top_ufgs_sections: list[str] = Field(default_factory=list)
    scan_pass: ScanPass = "description_only"
    parser_version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)
