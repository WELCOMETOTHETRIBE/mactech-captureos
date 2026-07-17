"""Pydantic contracts for LLM work-package adjudication (Slice 5).

The LLM decomposes an opportunity into bounded work packages, but every claim
must cite evidence IDs from the deterministically-assembled evidence set. A
post-parse validator drops any claim that references an unknown ID, so the model
cannot invent scope, deliverables, or citations.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

MACTECH_ROLES = ("prime", "sub", "advisor", "teammate", "required_hire", "not_fit")
CONFIDENCE = ("low", "medium", "high")


class WorkPackage(BaseModel):
    title: str
    scope_category: str = ""
    description: str = ""
    deliverables: list[str] = Field(default_factory=list)
    required_roles: list[str] = Field(default_factory=list)
    required_credentials: list[str] = Field(default_factory=list)
    mactech_role: Literal["prime", "sub", "advisor", "teammate", "required_hire", "not_fit"] = "sub"
    confidence: Literal["low", "medium", "high"] = "low"
    evidence_ids: list[str] = Field(default_factory=list)


class AdjudicationResult(BaseModel):
    customer_need: str = ""
    summary: str = ""
    work_packages: list[WorkPackage] = Field(default_factory=list)
    prompt_version: str = "wp-1.0.0"
    model: str | None = None


def validate_evidence_ids(
    result: AdjudicationResult, allowed_ids: set[str]
) -> tuple[AdjudicationResult, list[str]]:
    """Drop any evidence_id not in the deterministically-assembled set, and drop
    work packages left with no supporting evidence. Returns the cleaned result
    and the list of rejected (hallucinated) ids for auditing."""
    rejected: list[str] = []
    kept_packages: list[WorkPackage] = []
    for wp in result.work_packages:
        good = [eid for eid in wp.evidence_ids if eid in allowed_ids]
        bad = [eid for eid in wp.evidence_ids if eid not in allowed_ids]
        rejected.extend(bad)
        if not good:
            # No real evidence backs this package — discard it entirely.
            continue
        kept_packages.append(wp.model_copy(update={"evidence_ids": good}))
    cleaned = result.model_copy(update={"work_packages": kept_packages})
    return cleaned, rejected
