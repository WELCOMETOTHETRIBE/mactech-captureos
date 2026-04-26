"""Per-opportunity natural-language Q&A.

Phase 3 Week 11 (UX Sprint 3). Powers the "Ask Claude about this opp"
panel on the detail page. Uses Claude Sonnet for quality answers; the
context is opp + firm capabilities + past performance + score block.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse, StreamChunk

PROMPT_PATH = Path(__file__).parent / "prompts" / "ask_about_opp.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 700


# Starter questions surfaced as quick-tap buttons in the UI.
STARTERS: dict[str, str] = {
    "should_we_pursue": "Should we pursue this opportunity? Give a yes/no with the top 2 reasons each way.",
    "incumbent": "Who is the likely incumbent on this opportunity, and how strong is their position?",
    "win_probability": "What is our realistic win probability if we bid, and what would have to be true for us to win?",
    "must_haves": "What are the must-have requirements in this opportunity, and which of them does our firm satisfy today?",
    "teaming": "Should we prime, sub, or team on this? If teaming, what kind of partner do we need?",
}


@dataclass(frozen=True)
class AskOpportunityContext:
    title: str
    agency: str | None
    notice_type: str | None
    set_aside: str | None
    naics_code: str | None
    posted_at: datetime | None
    response_deadline: datetime | None
    description: str | None
    score: int | None
    score_breakdown: dict[str, int] | None
    why_it_matters: str | None
    incumbent_name: str | None
    incumbent_amount: float | None
    incumbent_end_date: str | None


@dataclass(frozen=True)
class AskFirmContext:
    tenant_name: str
    uei: str | None
    cage_code: str | None
    plan: str | None
    set_aside_certifications: list[str]
    capability_titles_and_summaries: list[tuple[str, str]] = field(default_factory=list)
    past_performance_summaries: list[str] = field(default_factory=list)
    teaming_partner_summaries: list[str] = field(default_factory=list)
    founder_summaries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AskInput:
    question: str
    starter_kind: str | None
    opportunity: AskOpportunityContext
    firm: AskFirmContext


def _format_opportunity(opp: AskOpportunityContext) -> str:
    lines = [
        "## OPPORTUNITY",
        f"Title: {opp.title}",
        f"Agency: {opp.agency or '(unspecified)'}",
        f"Notice type: {opp.notice_type or '(unspecified)'}",
        f"Set-aside: {opp.set_aside or 'unrestricted'}",
        f"NAICS: {opp.naics_code or '(unspecified)'}",
        f"Posted: {opp.posted_at.date().isoformat() if opp.posted_at else '(unspecified)'}",
        f"Response deadline: {opp.response_deadline.date().isoformat() if opp.response_deadline else '(unspecified)'}",
    ]
    if opp.score is not None:
        lines.append(f"Our score: {opp.score} / 100")
        if opp.score_breakdown:
            parts = ", ".join(
                f"{k}={v}" for k, v in sorted(opp.score_breakdown.items())
            )
            lines.append(f"Score breakdown: {parts}")
    if opp.why_it_matters:
        lines.append(f"Why it matters (auto-generated): {opp.why_it_matters}")
    if opp.incumbent_name:
        lines.append(f"Incumbent on file: {opp.incumbent_name}")
        if opp.incumbent_amount is not None:
            lines.append(f"  Cumulative obligations: ${opp.incumbent_amount:,.0f}")
        if opp.incumbent_end_date:
            lines.append(f"  Contract end: {opp.incumbent_end_date}")
    lines.append("")
    lines.append("### Description (verbatim from SAM.gov, may be truncated)")
    lines.append((opp.description or "(no description text on file)")[:5000])
    return "\n".join(lines)


def _format_firm(firm: AskFirmContext) -> str:
    lines = [
        "## RESPONDING FIRM",
        f"Name: {firm.tenant_name}",
        f"UEI: {firm.uei or '(pending)'}",
        f"CAGE: {firm.cage_code or '(pending)'}",
        f"Set-aside certifications: {', '.join(firm.set_aside_certifications) or '(none on file)'}",
    ]
    if firm.founder_summaries:
        lines.append("")
        lines.append("### Key personnel")
        for fs in firm.founder_summaries:
            lines.append(f"- {fs}")
    if firm.capability_titles_and_summaries:
        lines.append("")
        lines.append("### Capability statements")
        for title, summary in firm.capability_titles_and_summaries[:10]:
            lines.append(f"- **{title}**: {summary[:300]}")
    if firm.past_performance_summaries:
        lines.append("")
        lines.append("### Past performance")
        for pp in firm.past_performance_summaries[:8]:
            lines.append(f"- {pp[:300]}")
    if firm.teaming_partner_summaries:
        lines.append("")
        lines.append("### Active teaming partners")
        for tp in firm.teaming_partner_summaries[:8]:
            lines.append(f"- {tp[:200]}")
    return "\n".join(lines)


def build_user_message(inp: AskInput) -> str:
    return "\n\n".join(
        [
            f"USER QUESTION: {inp.question.strip()}",
            _format_opportunity(inp.opportunity),
            _format_firm(inp.firm),
            "Answer the user's question directly. Cap at 200 words. No headings, no bullet lists unless the question explicitly invites a list.",
        ]
    )


async def ask_about_opportunity(
    client: AnthropicLLMClient,
    inp: AskInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMResponse:
    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = build_user_message(inp)
    return await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"ask_about_opp:{PROMPT_VERSION}",
    )


async def stream_ask_about_opportunity(
    client: AnthropicLLMClient,
    inp: AskInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> AsyncIterator[StreamChunk]:
    """Streaming variant of `ask_about_opportunity`.

    Yields `StreamChunk(kind="delta", text=...)` events as the model
    composes, then a final `StreamChunk(kind="final", ...)` carrying
    the assembled answer + token usage. Same prompt + context path as
    the non-streaming version so cached prompts cost the same.
    """
    system_prompt = PROMPT_PATH.read_text().strip()
    user_message = build_user_message(inp)
    async for chunk in client.complete_stream(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"ask_about_opp:{PROMPT_VERSION}",
    ):
        yield chunk
