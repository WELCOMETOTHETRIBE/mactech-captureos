"""Plain-English explainer for jargon terms surfaced in the UI.

Phase 3 Week 10 (UX overhaul Sprint 2). Backs the "Explain this" right
rail on the opportunity detail page. Cheap, cached call to Claude Haiku.

Slug format: <kind>:<value>
  - "naics:541512"
  - "set_aside:SDVOSB"
  - "notice_type:sources_sought"
  - "score_component:naics_match"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

PROMPT_PATH = Path(__file__).parent / "prompts" / "explain_term.md"
PROMPT_VERSION = "v1"

# Canonical descriptions used to disambiguate the LLM's interpretation. Each
# kind has a small intro that grounds the prompt — without these, "set_aside:NONE"
# could be misinterpreted as "no set-aside data" instead of the actual code.
_KIND_INTROS: dict[str, str] = {
    "naics": (
        "NAICS code (North American Industry Classification System) used in "
        "federal contracting to classify the kind of work being procured. "
        "Each 6-digit code has its own SBA size standard determining whether "
        "a firm qualifies as a small business under that code."
    ),
    "set_aside": (
        "A set-aside designation on a federal opportunity. Set-asides reserve "
        "the procurement for a particular socioeconomic category of small "
        "business (SDVOSB, 8(a), HUBZone, WOSB, etc.) or for full-and-open "
        "competition."
    ),
    "notice_type": (
        "A SAM.gov notice type. Notice type signals where in the procurement "
        "lifecycle the opportunity sits — Sources Sought (market research), "
        "Solicitation (formal RFP), Award (already decided), Justification "
        "(sole-source rationale), etc."
    ),
    "score_component": (
        "A component of MacTech CaptureOS's opportunity-fit score. The "
        "platform scores each opportunity 0–100 against the firm's NAICS "
        "profile, set-aside fit, capability statements, and other signals; "
        "this is one of the constituent components."
    ),
    "agency": (
        "A federal agency or sub-agency that issues procurement notices."
    ),
    "term": (
        "A federal-contracting term encountered in the dashboard."
    ),
}


@dataclass(frozen=True)
class TermExplanation:
    label: str
    summary: str
    body: str
    response: LLMResponse


def parse_slug(slug: str) -> tuple[str, str]:
    """Split a slug 'kind:value' into (kind, value)."""
    if ":" in slug:
        kind, value = slug.split(":", 1)
        return kind.strip().lower(), value.strip()
    return "term", slug.strip()


def _human_label(kind: str, value: str) -> str:
    if kind == "naics":
        return f"NAICS {value}"
    if kind == "set_aside":
        return f"Set-aside: {value}"
    if kind == "notice_type":
        return f"Notice type: {value.replace('_', ' ').title()}"
    if kind == "score_component":
        return f"Score component: {value.replace('_', ' ').title()}"
    if kind == "agency":
        return value
    return value


async def explain_term(
    client: AnthropicLLMClient,
    slug: str,
    *,
    extra_context: str | None = None,
) -> TermExplanation:
    """Generate a plain-English explanation for a jargon slug.

    Result is short (Haiku, ~220 words). The API caches per (slug,
    prompt_version) so subsequent requests hit the DB.
    """
    kind, value = parse_slug(slug)
    intro = _KIND_INTROS.get(kind, _KIND_INTROS["term"])
    label = _human_label(kind, value)

    system_prompt = PROMPT_PATH.read_text().strip()

    user_lines = [
        f"Term to explain: {label}",
        f"Term kind: {kind}",
        f"Raw value: {value}",
        "",
        "Background on this kind of term:",
        intro,
    ]
    if extra_context:
        user_lines.append("")
        user_lines.append("Extra context for this specific term:")
        user_lines.append(extra_context)

    response = await client.complete(
        system=system_prompt,
        user="\n".join(user_lines),
        complexity="fast",
        max_tokens=350,
        purpose=f"explain_term:{PROMPT_VERSION}:{kind}",
    )

    text = response.text.strip()
    summary, body = _split_summary_body(text)

    return TermExplanation(
        label=label,
        summary=summary,
        body=body,
        response=response,
    )


def _split_summary_body(text: str) -> tuple[str, str]:
    """Split the model's output into (summary, body).

    Expected format: first non-empty line is the summary; everything after
    a blank line is the body. Falls back gracefully if the model deviates.
    """
    lines = text.splitlines()
    summary_lines: list[str] = []
    body_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not summary_lines and not stripped:
            continue  # skip leading blank lines
        if stripped:
            summary_lines.append(stripped)
        else:
            body_start = i + 1
            break
    summary = " ".join(summary_lines).strip()
    body = (
        "\n".join(lines[body_start:]).strip()
        if body_start is not None
        else ""
    )
    if not body:
        # Whole response is one paragraph — promote to body.
        return summary, summary
    return summary, body
