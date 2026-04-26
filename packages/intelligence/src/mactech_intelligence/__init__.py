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
from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse, StreamChunk
from mactech_intelligence.scoring import (
    OpportunityFacts,
    ScoringContext,
    ScoringResult,
    score_opportunity,
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
    "ExtractBriefInput",
    "ExtractedCapabilityStatement",
    "ExtractedPastPerformance",
    "FounderContext",
    "LLMResponse",
    "OpportunityContext",
    "OpportunityFacts",
    "PastPerformanceContext",
    "PastPerformanceExtractionError",
    "ScoringContext",
    "ScoringResult",
    "SourcesSoughtInput",
    "StreamChunk",
    "StructuredBrief",
    "TeamingPartnerContext",
    "TenantIdentity",
    "TermExplanationOut",
    "ask_about_opportunity",
    "context_hash",
    "explain_term",
    "extract_capability_statement",
    "extract_past_performance",
    "extract_structured_brief",
    "generate_sources_sought_draft",
    "generate_why_it_matters",
    "parse_explain_slug",
    "score_opportunity",
    "stream_ask_about_opportunity",
    "stream_sources_sought_draft",
]
