"""Generate the 'Why this matters' paragraph for the morning digest.

Wraps AnthropicLLMClient with the prompt template at prompts/why_it_matters.md.
Single function so the worker stays small.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

PROMPT_PATH = Path(__file__).parent / "prompts" / "why_it_matters.md"
PROMPT_VERSION = "v1"
SYSTEM_MARKER = "---SYSTEM---"
USER_MARKER = "---USER---"


@dataclass(frozen=True)
class WhyItMattersInput:
    title: str
    agency: str | None
    naics_code: str | None
    set_aside: str | None
    notice_type: str | None
    posted_at: datetime | None
    response_deadline: datetime | None
    description: str | None
    incumbent_name: str | None
    incumbent_amount: float | None
    incumbent_excluded: bool | None
    incumbent_end_date: date | None
    capability_titles: list[str]
    founder_slug: str | None
    founder_pillar: str | None


def _load_prompt() -> tuple[str, str]:
    raw = PROMPT_PATH.read_text()
    if SYSTEM_MARKER not in raw or USER_MARKER not in raw:
        raise RuntimeError(f"prompt file {PROMPT_PATH} missing required markers")
    _, rest = raw.split(SYSTEM_MARKER, 1)
    system, user = rest.split(USER_MARKER, 1)
    # Strip leading/trailing blank lines and # comment lines.
    system_clean = "\n".join(
        line for line in system.strip().splitlines() if not line.startswith("#")
    )
    user_clean = "\n".join(line for line in user.strip().splitlines() if not line.startswith("#"))
    return system_clean, user_clean


def _format_incumbent(inp: WhyItMattersInput) -> str:
    if not inp.incumbent_name:
        return "  (no incumbent identified — likely a fresh requirement)"
    parts = [f"  Name: {inp.incumbent_name}"]
    if inp.incumbent_amount is not None:
        parts.append(f"  Cumulative obligations in this NAICS+agency: ${inp.incumbent_amount:,.0f}")
    if inp.incumbent_end_date is not None:
        parts.append(f"  Current PoP end date: {inp.incumbent_end_date.isoformat()}")
    if inp.incumbent_excluded is True:
        parts.append("  Exclusions status: ON THE DEBARMENT LIST — strong recompete signal")
    elif inp.incumbent_excluded is False:
        parts.append("  Exclusions status: clean")
    return "\n".join(parts)


def _format_capabilities(inp: WhyItMattersInput) -> str:
    if not inp.capability_titles:
        return "  (no high-similarity capability statements matched)"
    return "\n".join(f"  - {t}" for t in inp.capability_titles[:3])


async def generate_why_it_matters(
    client: AnthropicLLMClient,
    inp: WhyItMattersInput,
) -> LLMResponse:
    system_template, user_template = _load_prompt()
    user = user_template.format(
        title=inp.title,
        agency=inp.agency or "(not specified)",
        naics_code=inp.naics_code or "(not specified)",
        set_aside=inp.set_aside or "(unrestricted)",
        notice_type=inp.notice_type or "(not specified)",
        posted_at=inp.posted_at.isoformat() if inp.posted_at else "(not specified)",
        response_deadline=(
            inp.response_deadline.isoformat() if inp.response_deadline else "(not specified)"
        ),
        description=(inp.description or "(not provided)")[:1500],
        incumbent_block=_format_incumbent(inp),
        capability_block=_format_capabilities(inp),
        founder_slug=inp.founder_slug or "(unassigned)",
        founder_pillar=inp.founder_pillar or "(not specified)",
    )
    return await client.complete(
        system=system_template,
        user=user,
        complexity="fast",
        max_tokens=500,
        purpose=f"why_it_matters:{PROMPT_VERSION}",
    )
