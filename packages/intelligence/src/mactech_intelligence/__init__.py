"""Scoring, parsing, compliance matrix generation, LLM client abstraction.

Per docs/AGENT_ARCHITECTURE.md, Phase 1 routes all traffic through
AnthropicAPIClient with a single platform key. AgentSDKClient is
stubbed until the Phase 5 triggers ($300/mo MacTech-only spend or
Prime/Enterprise volume) are hit.
"""

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse
from mactech_intelligence.scoring import (
    ScoringContext,
    ScoringResult,
    score_opportunity,
)
from mactech_intelligence.why_it_matters import generate_why_it_matters

__all__ = [
    "AnthropicLLMClient",
    "LLMResponse",
    "ScoringContext",
    "ScoringResult",
    "score_opportunity",
    "generate_why_it_matters",
]
