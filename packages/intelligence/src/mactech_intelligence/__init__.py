"""Scoring, parsing, compliance matrix generation, LLM client abstraction.

Per docs/AGENT_ARCHITECTURE.md, Phase 1 routes all traffic through
AnthropicAPIClient with a single platform key. AgentSDKClient is
stubbed until the Phase 5 triggers ($300/mo MacTech-only spend or
Prime/Enterprise volume) are hit.
"""

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse
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
)
from mactech_intelligence.why_it_matters import generate_why_it_matters

__all__ = [
    "AnthropicLLMClient",
    "CapabilityContext",
    "FounderContext",
    "LLMResponse",
    "OpportunityContext",
    "OpportunityFacts",
    "PastPerformanceContext",
    "ScoringContext",
    "ScoringResult",
    "SourcesSoughtInput",
    "TeamingPartnerContext",
    "TenantIdentity",
    "context_hash",
    "generate_sources_sought_draft",
    "generate_why_it_matters",
    "score_opportunity",
]
