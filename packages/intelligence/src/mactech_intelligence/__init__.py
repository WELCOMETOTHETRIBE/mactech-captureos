"""Scoring, parsing, compliance matrix generation, LLM client abstraction.

Per docs/AGENT_ARCHITECTURE.md, Phase 1 routes all traffic through
AnthropicAPIClient with a single platform key. AgentSDKClient is
stubbed until the Phase 5 triggers ($300/mo MacTech-only spend or
Prime/Enterprise volume) are hit.
"""

from mactech_intelligence.ask_about_opportunity import (
    STARTERS as ASK_STARTERS,
    AskFirmContext,
    AskInput,
    AskOpportunityContext,
    ask_about_opportunity,
    stream_ask_about_opportunity,
)
from mactech_intelligence.explain_term import (
    TermExplanation as TermExplanationOut,
    explain_term,
    parse_slug as parse_explain_slug,
)
from mactech_intelligence.extract_brief import (
    BriefExtractionError,
    ExtractBriefInput,
    StructuredBrief,
    extract_structured_brief,
)
from mactech_intelligence.extract_capability_statement import (
    CapabilityExtractionError,
    ExtractedCapabilityStatement,
    extract_capability_statement,
)
from mactech_intelligence.extract_past_performance import (
    ExtractedPastPerformance,
    PastPerformanceExtractionError,
    extract_past_performance,
)
from mactech_intelligence.extract_solicitation import (
    ExtractedComplianceItem,
    ExtractedEvaluationPassFailItem,
    ExtractedEvaluationScoredFactor,
    ExtractedRequirementItem,
    ExtractSolicitationInput,
    SolicitationExtractionError,
    SolicitationExtractionResult,
    extract_solicitation,
)
from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse, StreamChunk
from mactech_intelligence.clause_detector import (
    ClauseFindings,
    detect as detect_clauses,
)
from mactech_intelligence.scoring import (
    OpportunityFacts,
    ScoringContext,
    ScoringResult,
    score_opportunity,
)
from mactech_intelligence.scoring_high_moat import (
    HighMoatConfig,
    HighMoatFacts,
    HighMoatResult,
    score_high_moat,
)
from mactech_intelligence.sources_sought_drafter import (
    CapabilityContext,
    FounderContext,
    OpportunityContext,
    PastPerformanceContext,
    SourcesSoughtInput,
    TeamingPartnerContext,
    TenantIdentity,
    context_hash,
    generate_sources_sought_draft,
    stream_sources_sought_draft,
)
from mactech_intelligence.why_it_matters import generate_why_it_matters

__all__ = [
    "ASK_STARTERS",
    "AnthropicLLMClient",
    "AskFirmContext",
    "AskInput",
    "AskOpportunityContext",
    "BriefExtractionError",
    "CapabilityContext",
    "CapabilityExtractionError",
    "ClauseFindings",
    "ExtractBriefInput",
    "ExtractSolicitationInput",
    "ExtractedCapabilityStatement",
    "ExtractedComplianceItem",
    "ExtractedEvaluationPassFailItem",
    "ExtractedEvaluationScoredFactor",
    "ExtractedPastPerformance",
    "ExtractedRequirementItem",
    "FounderContext",
    "HighMoatConfig",
    "HighMoatFacts",
    "HighMoatResult",
    "LLMResponse",
    "OpportunityContext",
    "OpportunityFacts",
    "PastPerformanceContext",
    "PastPerformanceExtractionError",
    "ScoringContext",
    "ScoringResult",
    "SolicitationExtractionError",
    "SolicitationExtractionResult",
    "SourcesSoughtInput",
    "StreamChunk",
    "StructuredBrief",
    "TeamingPartnerContext",
    "TenantIdentity",
    "TermExplanationOut",
    "ask_about_opportunity",
    "context_hash",
    "detect_clauses",
    "explain_term",
    "extract_capability_statement",
    "extract_past_performance",
    "extract_solicitation",
    "extract_structured_brief",
    "generate_sources_sought_draft",
    "generate_why_it_matters",
    "parse_explain_slug",
    "score_high_moat",
    "score_opportunity",
    "stream_ask_about_opportunity",
    "stream_sources_sought_draft",
]
