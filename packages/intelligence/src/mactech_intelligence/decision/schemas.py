"""Pydantic contracts for the decision layer.

These are the persisted shapes (mirrored by the DB tables) and the interchange
types other systems consume. Kept in Pydantic so any future LLM-produced
decision fragment validates against the same contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from mactech_intelligence.decision.lanes import PursuitLane

FORMULA_VERSION = "1.0.0"


class EvidenceCitation(BaseModel):
    """A pointer back to the evidence a claim rests on."""

    kind: str  # "signal" | "gate" | "document" | "award"
    label: str
    document_id: str | None = None
    page_number: int | None = None
    section_heading: str | None = None
    snippet: str | None = None


class GateRecord(BaseModel):
    gate_code: str
    status: str  # pass | fail | unknown | waived
    severity: str  # hard | soft
    reason_code: str | None = None
    detail: str = ""
    source: str = "deterministic"


class DecisionVector(BaseModel):
    relevance_score: int = Field(ge=0, le=100, default=0)
    prime_fit_score: int = Field(ge=0, le=100, default=0)
    subcontract_fit_score: int = Field(ge=0, le=100, default=0)
    winability_score: int = Field(ge=0, le=100, default=0)
    deliverability_score: int = Field(ge=0, le=100, default=0)
    strategic_value_score: int = Field(ge=0, le=100, default=0)
    urgency_score: int = Field(ge=0, le=100, default=0)
    evidence_completeness_score: int = Field(ge=0, le=100, default=0)
    overall_priority_score: int = Field(ge=0, le=100, default=0)


class LaneDecision(BaseModel):
    pursuit_lane: PursuitLane
    reason_codes: list[str] = Field(default_factory=list)
    confidence: str = "medium"  # low | medium | high
    lane_weight_profile: str = "prime"
    formula_version: str = FORMULA_VERSION
    vector: DecisionVector
    gates: list[GateRecord] = Field(default_factory=list)
    evidence: list[EvidenceCitation] = Field(default_factory=list)
