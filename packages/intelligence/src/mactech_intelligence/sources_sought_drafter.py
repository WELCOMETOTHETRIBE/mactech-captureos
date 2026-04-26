"""Sources Sought response drafter.

Phase 3 Week 9. Wraps AnthropicLLMClient with the prompt template at
prompts/sources_sought.md (system) + a structured user payload built
from the opportunity, the firm's capability statements, past performance,
teaming partners, and tenant identity.

The prompt is deliberately conservative: "Do not invent past performance,
certifications, or facts not present in the context." That keeps the
draft citation-grounded and gives the founder editor a real starting
point rather than hallucinated polish.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse, StreamChunk

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "sources_sought.md"
PROMPT_VERSION = "v1"
DEFAULT_MAX_TOKENS = 4000


@dataclass(frozen=True)
class TenantIdentity:
    name: str
    uei: str | None = None
    cage_code: str | None = None
    plan: str | None = None
    primary_contact_email: str | None = None
    primary_contact_name: str | None = None
    set_aside_certifications: list[str] = field(default_factory=list)
    address: str | None = None


@dataclass(frozen=True)
class FounderContext:
    slug: str
    full_name: str
    title: str
    pillar: str
    email: str | None


@dataclass(frozen=True)
class CapabilityContext:
    slug: str
    title: str
    summary: str
    related_naics: list[str]
    related_founder_slugs: list[str]


@dataclass(frozen=True)
class PastPerformanceContext:
    title: str
    customer_agency: str | None
    customer_office: str | None
    contract_number: str | None
    role: str
    period_start: date | None
    period_end: date | None
    contract_value: float | None
    naics_code: str | None
    summary: str
    keywords: list[str]


@dataclass(frozen=True)
class TeamingPartnerContext:
    name: str
    uei: str | None
    capabilities: list[str]
    naics_codes: list[str]
    set_aside_certifications: list[str]
    notes: str | None


@dataclass(frozen=True)
class OpportunityContext:
    notice_id: str
    title: str
    notice_type: str | None
    set_aside: str | None
    set_aside_description: str | None
    naics_code: str | None
    agency: str | None
    solicitation_number: str | None
    posted_at: datetime | None
    response_deadline: datetime | None
    description: str | None


@dataclass(frozen=True)
class SourcesSoughtInput:
    opportunity: OpportunityContext
    tenant: TenantIdentity
    founders: list[FounderContext]
    capabilities: list[CapabilityContext]
    past_performance: list[PastPerformanceContext]
    teaming_partners: list[TeamingPartnerContext]
    custom_instructions: str | None = None


def _load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text().strip()


def _format_date(d: date | datetime | None) -> str:
    if d is None:
        return "(not specified)"
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def _format_money(n: float | None) -> str:
    if n is None:
        return "(not specified)"
    return f"${n:,.0f}"


def _format_list(items: list[str], empty: str = "(none)") -> str:
    if not items:
        return empty
    return ", ".join(items)


def _format_opportunity(opp: OpportunityContext) -> str:
    return (
        "## OPPORTUNITY\n"
        f"Title: {opp.title}\n"
        f"Notice ID: {opp.notice_id}\n"
        f"Notice type: {opp.notice_type or '(unspecified)'}\n"
        f"Agency: {opp.agency or '(unspecified)'}\n"
        f"Solicitation #: {opp.solicitation_number or '(none)'}\n"
        f"NAICS: {opp.naics_code or '(unspecified)'}\n"
        f"Set-aside: {opp.set_aside or 'unrestricted'}"
        f"{' — ' + opp.set_aside_description if opp.set_aside_description else ''}\n"
        f"Posted: {_format_date(opp.posted_at)}\n"
        f"Response deadline: {_format_date(opp.response_deadline)}\n\n"
        "### Description (verbatim from SAM.gov)\n"
        f"{(opp.description or '(no description text on file)')[:6000]}\n"
    )


def _format_tenant(t: TenantIdentity) -> str:
    return (
        "## RESPONDING FIRM\n"
        f"Name: {t.name}\n"
        f"UEI: {t.uei or '(pending)'}\n"
        f"CAGE: {t.cage_code or '(pending)'}\n"
        f"Set-aside certifications: {_format_list(t.set_aside_certifications, '(none on file)')}\n"
        f"Primary POC: {t.primary_contact_name or '(use point-of-contact section to fill)'}"
        f"{' / ' + t.primary_contact_email if t.primary_contact_email else ''}\n"
        f"Address: {t.address or '(not on file)'}\n"
    )


def _format_founders(fs: list[FounderContext]) -> str:
    if not fs:
        return "## KEY PERSONNEL\n(none on file)\n"
    out = ["## KEY PERSONNEL"]
    for f in fs:
        line = f"- {f.full_name}, {f.title} ({f.pillar} pillar)"
        if f.email:
            line += f" — {f.email}"
        out.append(line)
    return "\n".join(out) + "\n"


def _format_capabilities(caps: list[CapabilityContext]) -> str:
    if not caps:
        return "## CAPABILITY STATEMENTS\n(no capability statements on file)\n"
    out = ["## CAPABILITY STATEMENTS"]
    for c in caps:
        out.append(f"### {c.title}")
        out.append(c.summary.strip())
        if c.related_naics:
            out.append(f"NAICS: {_format_list(c.related_naics)}")
        if c.related_founder_slugs:
            out.append(f"Owners: {_format_list(c.related_founder_slugs)}")
        out.append("")
    return "\n".join(out)


def _format_past_performance(pp: list[PastPerformanceContext]) -> str:
    if not pp:
        return (
            "## PAST PERFORMANCE\n"
            "(no past-performance records on file. Note this in the response — "
            "do not invent prior contracts.)\n"
        )
    out = ["## PAST PERFORMANCE"]
    for p in pp:
        out.append(f"### {p.title} ({p.role})")
        if p.customer_agency:
            cust = p.customer_agency + (f" / {p.customer_office}" if p.customer_office else "")
            out.append(f"Customer: {cust}")
        if p.contract_number:
            out.append(f"Contract #: {p.contract_number}")
        if p.naics_code:
            out.append(f"NAICS: {p.naics_code}")
        if p.period_start or p.period_end:
            out.append(
                f"Period: {_format_date(p.period_start)} – {_format_date(p.period_end)}"
            )
        if p.contract_value is not None:
            out.append(f"Value: {_format_money(p.contract_value)}")
        out.append("")
        out.append(p.summary.strip())
        if p.keywords:
            out.append(f"Keywords: {_format_list(p.keywords)}")
        out.append("")
    return "\n".join(out)


def _format_teaming(partners: list[TeamingPartnerContext]) -> str:
    if not partners:
        return (
            "## TEAMING PARTNERS\n"
            "(no teaming partners on file. Omit the teaming section unless the "
            "opportunity explicitly requires multi-vendor capability you cannot "
            "self-perform.)\n"
        )
    out = ["## TEAMING PARTNERS"]
    for p in partners:
        out.append(f"### {p.name}")
        if p.uei:
            out.append(f"UEI: {p.uei}")
        if p.capabilities:
            out.append(f"Capabilities: {_format_list(p.capabilities)}")
        if p.naics_codes:
            out.append(f"NAICS: {_format_list(p.naics_codes)}")
        if p.set_aside_certifications:
            out.append(
                f"Set-aside certs: {_format_list(p.set_aside_certifications)}"
            )
        if p.notes:
            out.append(f"Notes: {p.notes}")
        out.append("")
    return "\n".join(out)


def _build_user_message(inp: SourcesSoughtInput) -> str:
    parts = [
        "Draft a Sources Sought response for the opportunity below using only "
        "the firm context provided. Output as clean markdown per the system "
        "instructions.",
        "",
        _format_opportunity(inp.opportunity),
        _format_tenant(inp.tenant),
        _format_founders(inp.founders),
        _format_capabilities(inp.capabilities),
        _format_past_performance(inp.past_performance),
        _format_teaming(inp.teaming_partners),
    ]
    if inp.custom_instructions:
        parts.append("## ADDITIONAL INSTRUCTIONS FROM THE USER")
        parts.append(inp.custom_instructions.strip())
        parts.append("")
    return "\n\n".join(parts)


def context_hash(inp: SourcesSoughtInput) -> str:
    """Stable hash over the inputs that drove this draft.

    Used by the API to dedupe regenerations: if the user clicks "Generate"
    again with the same context and same custom_instructions, we can show a
    "this would produce the same draft" affordance instead of burning tokens.
    """
    payload = {
        "opp_notice_id": inp.opportunity.notice_id,
        "tenant_uei": inp.tenant.uei,
        "tenant_name": inp.tenant.name,
        "founders": sorted(f.slug for f in inp.founders),
        "capabilities": sorted(c.slug for c in inp.capabilities),
        "past_performance": sorted(p.title for p in inp.past_performance),
        "teaming_partners": sorted(p.name for p in inp.teaming_partners),
        "custom_instructions": (inp.custom_instructions or "").strip(),
        "version": PROMPT_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode()
    ).hexdigest()


async def generate_sources_sought_draft(
    client: AnthropicLLMClient,
    inp: SourcesSoughtInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMResponse:
    """Call Claude with the system prompt + structured firm context.

    Uses MODEL_SMART (claude-sonnet-4-6) per docs/DATA_SOURCES.md §4.1 — the
    model intended for proposal drafting tasks.
    """
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(inp)
    return await client.complete(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"sources_sought_draft:{PROMPT_VERSION}",
    )


async def stream_sources_sought_draft(
    client: AnthropicLLMClient,
    inp: SourcesSoughtInput,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> AsyncIterator[StreamChunk]:
    """Streaming variant of `generate_sources_sought_draft`.

    Yields `StreamChunk(kind="delta", text=...)` events as the model
    composes, then a final `StreamChunk(kind="final", ...)` carrying the
    assembled markdown + token usage. Same prompt + context path as the
    non-streaming version so prompt-cache hits are identical.
    """
    system_prompt = _load_system_prompt()
    user_message = _build_user_message(inp)
    async for chunk in client.complete_stream(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=f"sources_sought_draft:{PROMPT_VERSION}",
    ):
        yield chunk
