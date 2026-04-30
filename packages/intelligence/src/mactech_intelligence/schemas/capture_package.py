"""Capture Package schema — the CaptureOS → ProposalOS handoff artifact.

This is integration contract #1 in the five-app ecosystem (see
``docs/00_Ecosystem_Overview.md``). When CaptureOS decides "we're bidding"
on an opportunity, it produces a Capture Package: a versioned, self-contained
snapshot of everything CaptureOS knows about the pursuit. ProposalOS imports
that snapshot and runs the proposal effort from there.

Treat this schema as a published API:

* Bumps to ``CAPTURE_PACKAGE_SCHEMA_VERSION`` follow semver. Within a major
  version, additions are backwards-compatible (new optional fields).
* Removals or type changes require a major version bump.
* Every section is self-describing: data we have is populated, data we
  don't yet have is explicitly empty/null. Consumers read
  ``completeness.gaps`` to understand what's missing in any given package.

Sections mirror the V1 scope in ``docs/CaptureOS_Requirements.md`` Section H.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CAPTURE_PACKAGE_SCHEMA_VERSION = "1.0.0"


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------


class OpportunitySection(_Base):
    """Core opportunity metadata pulled from SAM.gov / source feed."""

    notice_id: str
    source: str
    solicitation_number: str | None = None
    title: str
    notice_type: str | None = None
    agency: str | None = None
    subagency: str | None = None
    office: str | None = None
    naics_code: str | None = None
    set_aside: str | None = None
    contract_type: str | None = None
    response_deadline: str | None = None  # ISO 8601
    posted_at: str | None = None  # ISO 8601
    estimated_value_low: float | None = None
    estimated_value_high: float | None = None
    place_of_performance: dict | None = None
    submission_method: str | None = None
    description_url: str | None = None
    description_text_excerpt: str | None = Field(
        default=None,
        description="First ~4000 chars of the description for quick reference. "
        "Full text lives in solicitation.files when ingested.",
    )


# ---------------------------------------------------------------------------
# Solicitation files + amendments + Q&A
# ---------------------------------------------------------------------------


class SolicitationFile(_Base):
    """A single solicitation document or attachment.

    V1 note: CaptureOS does not yet maintain a separate documents table.
    Today this section reports the primary description URL only; full file
    enumeration will populate as the solicitation decoder (Section C) is
    built out.
    """

    file_id: str | None = None
    name: str
    url: str | None = None
    kind: Literal[
        "solicitation",
        "attachment",
        "exhibit",
        "amendment",
        "wage_determination",
        "qa_document",
        "drawing",
        "dd254",
        "other",
    ] = "other"
    posted_at: str | None = None
    sha256: str | None = None


class SolicitationSection(_Base):
    primary_description_url: str | None = None
    primary_description_text_excerpt: str | None = None
    files: list[SolicitationFile] = Field(default_factory=list)
    amendments: list[SolicitationFile] = Field(default_factory=list)
    raw_payload_available: bool = False


# ---------------------------------------------------------------------------
# Compliance + Requirements matrices
# ---------------------------------------------------------------------------


class ComplianceItem(_Base):
    """A single 'shall' from Section L (instructions to offerors)."""

    id: str
    statement: str
    section_l_citation: str | None = None
    pass_fail: bool = False
    notes: str | None = None


class ComplianceMatrixSection(_Base):
    items: list[ComplianceItem] = Field(default_factory=list)
    source_documents: list[str] = Field(default_factory=list)
    last_generated_at: str | None = None
    status: Literal["not_generated", "generated", "stale"] = "not_generated"


class RequirementItem(_Base):
    """A single technical/operational/security obligation from SOW/PWS/CDRLs."""

    id: str
    statement: str
    source_citation: str | None = None
    category: Literal[
        "technical",
        "operational",
        "security",
        "staffing",
        "performance",
        "reporting",
        "other",
    ] = "other"


class RequirementsMatrixSection(_Base):
    items: list[RequirementItem] = Field(default_factory=list)
    last_generated_at: str | None = None
    status: Literal["not_generated", "generated", "stale"] = "not_generated"


# ---------------------------------------------------------------------------
# Evaluation factors (Section M)
# ---------------------------------------------------------------------------


class PassFailItem(_Base):
    statement: str
    source_citation: str | None = None


class ScoredFactor(_Base):
    name: str
    weight: float | None = None
    description: str | None = None
    source_citation: str | None = None


class EvaluationSection(_Base):
    pass_fail_items: list[PassFailItem] = Field(default_factory=list)
    scored_factors: list[ScoredFactor] = Field(default_factory=list)
    status: Literal["not_extracted", "extracted"] = "not_extracted"


# ---------------------------------------------------------------------------
# Cyber clauses + posture snapshot from Codex
# ---------------------------------------------------------------------------


class CyberPostureSnapshot(_Base):
    """Snapshot of cyber posture from Codex at decision time (Contract #4)."""

    sprs_score: int | None = None
    sprs_max: int | None = None
    sprs_assessment_date: str | None = None  # ISO date
    sprs_source_url: str | None = None
    cmmc_level_current: str | None = None
    source: Literal["codex", "stub"] = "codex"
    snapshot_at: str  # ISO datetime when this snapshot was captured


class CyberSection(_Base):
    clauses_identified: list[str] = Field(
        default_factory=list,
        description="FAR/DFARS clause numbers parsed from the solicitation.",
    )
    cmmc_level_required: str | None = None
    handles_cui: bool | None = None
    handles_fci: bool | None = None
    handles_itar: bool | None = None
    posture_snapshot: CyberPostureSnapshot | None = None
    sufficiency: Literal["sufficient", "gap", "unknown"] = "unknown"
    sufficiency_notes: str | None = None


# ---------------------------------------------------------------------------
# Capture strategy (agency / incumbent / competitor / customer priorities)
# ---------------------------------------------------------------------------


class IncumbentSummary(_Base):
    name: str | None = None
    uei: str | None = None
    contract_id: str | None = None
    end_date: str | None = None
    award_amount: float | None = None
    cleared_exclusions: bool | None = None


class CaptureStrategySection(_Base):
    agency_brief: str | None = None
    scope_one_sentence: str | None = None
    incumbent: IncumbentSummary | None = None
    likely_competitors: list[str] = Field(default_factory=list)
    customer_priorities: str | None = None
    must_have_requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    red_flags_for_small_biz: list[str] = Field(default_factory=list)
    suggested_team_roles: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Win strategy (themes + discriminators)
# ---------------------------------------------------------------------------


class WinStrategySection(_Base):
    win_themes: list[str] = Field(default_factory=list)
    discriminators: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Library refs — past performance, key personnel, teaming partners
# ---------------------------------------------------------------------------


class PastPerformanceRef(_Base):
    id: str
    title: str
    customer_agency: str | None = None
    customer_office: str | None = None
    contract_number: str | None = None
    role: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    contract_value: float | None = None
    summary: str | None = None
    keywords: list[str] = Field(default_factory=list)


class PastPerformanceSection(_Base):
    selected: list[PastPerformanceRef] = Field(default_factory=list)
    library_size: int = 0
    selection_method: Literal["manual", "ai_suggested", "none"] = "none"


class KeyPersonRef(_Base):
    id: str
    slug: str
    full_name: str
    title: str | None = None
    pillar: str | None = None
    bio: str | None = None
    email: str | None = None
    areas_of_expertise: list[str] = Field(default_factory=list)


class KeyPersonnelSection(_Base):
    selected: list[KeyPersonRef] = Field(default_factory=list)
    library_size: int = 0


class GovernanceDocState(_Base):
    """State of legal documents between tenant and a teaming counterparty.

    GovernanceOS is the source of truth (Contract #2). Until GovernanceOS
    exists, every field is None and ``source`` is ``"stub"``.
    """

    mnda_executed: bool | None = None
    mnda_signed_at: str | None = None
    teaming_agreement_executed: bool | None = None
    teaming_agreement_signed_at: str | None = None
    subcontract_executed: bool | None = None
    subcontract_signed_at: str | None = None
    last_synced_at: str | None = None
    source: Literal["governance_os", "stub"] = "stub"


class TeamingPartnerRef(_Base):
    id: str
    name: str
    uei: str | None = None
    cage_code: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    naics_codes: list[str] = Field(default_factory=list)
    set_aside_certifications: list[str] = Field(default_factory=list)
    contact_name: str | None = None
    contact_email: str | None = None
    governance_doc_state: GovernanceDocState = Field(
        default_factory=GovernanceDocState
    )


class TeamingPartnersSection(_Base):
    selected: list[TeamingPartnerRef] = Field(default_factory=list)
    library_size: int = 0


# ---------------------------------------------------------------------------
# Bid decision memo
# ---------------------------------------------------------------------------


class BidDecisionSection(_Base):
    decision: Literal["bid", "no_bid", "pending"] = "pending"
    pursuit_stage: str | None = None
    decided_at: str | None = None
    decider_user_id: str | None = None
    decider_founder_slug: str | None = None
    rationale: str | None = None
    score: int | None = None
    score_breakdown: dict | None = None


# ---------------------------------------------------------------------------
# Governance readiness snapshot (from GovernanceOS, contract #2)
# ---------------------------------------------------------------------------


class GovernanceReadinessSection(_Base):
    """Snapshot of corporate readiness facts from GovernanceOS at decision time.

    Until GovernanceOS exists, every field is None and ``source`` is
    ``"stub"``. CaptureOS still publishes the section so ProposalOS clients
    have a stable shape to deserialize.
    """

    accounting_system_dcaa_ready: bool | None = None
    accounting_system_provider: str | None = None
    fcl_status: str | None = None
    fcl_level: str | None = None
    set_asides_held: list[str] = Field(default_factory=list)
    e_verify_enrolled: bool | None = None
    reps_certs_current: bool | None = None
    reps_certs_last_renewed_at: str | None = None
    snapshot_at: str | None = None
    source: Literal["governance_os", "stub"] = "stub"


# ---------------------------------------------------------------------------
# Q&A history
# ---------------------------------------------------------------------------


class QAEntry(_Base):
    id: str
    question: str
    answer: str | None = None
    asked_by_founder_slug: str | None = None
    submitted_at: str | None = None
    answered_at: str | None = None
    starter_kind: str | None = None


class QAHistorySection(_Base):
    entries: list[QAEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Completeness summary
# ---------------------------------------------------------------------------


class PackageCompleteness(_Base):
    """Self-reported completeness so consumers know what's real vs. empty."""

    overall_pct: float = Field(
        ge=0.0,
        le=100.0,
        description="Heuristic 0-100 of how filled-out the package is.",
    )
    sections_complete: list[str] = Field(default_factory=list)
    sections_partial: list[str] = Field(default_factory=list)
    sections_missing: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(
        default_factory=list,
        description="Human-readable list of what's missing or stubbed.",
    )


# ---------------------------------------------------------------------------
# Top-level package
# ---------------------------------------------------------------------------


class CapturePackage(_Base):
    """The complete CaptureOS → ProposalOS handoff artifact.

    Versioned. Sections that aren't yet captured by CaptureOS publish empty
    or null values rather than being omitted entirely — the schema is the
    contract, completeness is observable.
    """

    schema_version: str = CAPTURE_PACKAGE_SCHEMA_VERSION
    generated_at: str  # ISO 8601 UTC
    tenant_id: str
    tenant_slug: str
    pursuit_id: str

    opportunity: OpportunitySection
    solicitation: SolicitationSection = Field(default_factory=SolicitationSection)
    compliance_matrix: ComplianceMatrixSection = Field(
        default_factory=ComplianceMatrixSection
    )
    requirements_matrix: RequirementsMatrixSection = Field(
        default_factory=RequirementsMatrixSection
    )
    evaluation: EvaluationSection = Field(default_factory=EvaluationSection)
    cyber: CyberSection = Field(default_factory=CyberSection)
    capture_strategy: CaptureStrategySection = Field(
        default_factory=CaptureStrategySection
    )
    win_strategy: WinStrategySection = Field(default_factory=WinStrategySection)
    past_performance: PastPerformanceSection = Field(
        default_factory=PastPerformanceSection
    )
    key_personnel: KeyPersonnelSection = Field(default_factory=KeyPersonnelSection)
    teaming_partners: TeamingPartnersSection = Field(
        default_factory=TeamingPartnersSection
    )
    bid_decision: BidDecisionSection = Field(default_factory=BidDecisionSection)
    governance_readiness: GovernanceReadinessSection = Field(
        default_factory=GovernanceReadinessSection
    )
    qa_history: QAHistorySection = Field(default_factory=QAHistorySection)

    completeness: PackageCompleteness


# Helper: parse a date or datetime to ISO 8601 string, tolerant of None.
def to_iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
