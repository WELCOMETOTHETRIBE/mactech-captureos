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
    "set_aside_cert": (
        "A set-aside certification a tenant claims to hold (e.g., SDVOSB, "
        "8(a), WOSB, HUBZone). Required to legitimately bid set-aside "
        "opportunities reserved for that category. Certifications are issued "
        "by SBA, the VA, or self-attested via SAM.gov."
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
    "clause": (
        "A FAR (Federal Acquisition Regulation) or DFARS (Defense FAR "
        "Supplement) clause cited in a federal solicitation. Clauses define "
        "obligations the contractor accepts when awarded — cybersecurity "
        "controls, reporting cadence, data-handling rules, flow-downs to "
        "subcontractors, etc. The clause number is the primary key (e.g., "
        "FAR 52.204-21, DFARS 252.204-7012)."
    ),
    "cmmc": (
        "A Cybersecurity Maturity Model Certification (CMMC) level required "
        "by a DoD solicitation. CMMC 2.0 has three levels: Level 1 (basic, "
        "FAR 52.204-21 / FCI), Level 2 (advanced, NIST SP 800-171 / CUI, "
        "third-party assessor for prioritized contracts), Level 3 (expert, "
        "NIST SP 800-172 + DIBCAC assessment)."
    ),
    "section": (
        "A section reference inside a federal solicitation. Section L is the "
        "Instructions to Offerors (what the proposal must say); Section M is "
        "the Evaluation Factors for Award (how the proposal is graded). "
        "SOW = Statement of Work, PWS = Performance Work Statement, "
        "SOO = Statement of Objectives, CDRL = Contract Data Requirements "
        "List."
    ),
    "sprs": (
        "Supplier Performance Risk System — DoD's database of self-reported "
        "NIST SP 800-171 implementation scores. DFARS 252.204-7019 / 7020 "
        "require contractors handling CUI to post a current SPRS score "
        "(within 3 years). Scores range from -203 (worst) to +110 (full "
        "implementation of all 110 controls)."
    ),
    "cui": (
        "Controlled Unclassified Information — federal data that requires "
        "safeguarding under government rules but isn't classified. Contracts "
        "involving CUI trigger DFARS 252.204-7012 (cyber incident reporting), "
        "NIST 800-171 controls, and CMMC Level 2."
    ),
    "fci": (
        "Federal Contract Information — basic information not for public "
        "release that's provided by or generated for the government. FAR "
        "52.204-21 imposes 15 basic safeguards on systems handling FCI."
    ),
    "itar": (
        "International Traffic in Arms Regulations — controls on export of "
        "defense articles, services, and technical data. ITAR-restricted "
        "work generally requires US-person staffing and registration with "
        "the State Department's DDTC."
    ),
    "uei": (
        "Unique Entity Identifier — the 12-character alphanumeric ID SAM.gov "
        "assigns each registered entity. UEI replaced DUNS in April 2022 "
        "and is required for any federal award."
    ),
    "cage": (
        "Commercial and Government Entity code — a 5-character DLA-assigned "
        "code identifying companies that supply the federal government. "
        "Auto-issued during SAM.gov registration. Required for facility "
        "clearances and most DoD contracts."
    ),
    "fcl": (
        "Facility Clearance — DCSA-issued clearance authorizing a contractor "
        "to access classified information at a specific level (Confidential, "
        "Secret, Top Secret). Without an FCL at the required level, you "
        "cannot legally bid solicitations that handle classified data."
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
    if kind == "set_aside_cert":
        return f"{value} certification"
    if kind == "notice_type":
        return f"Notice type: {value.replace('_', ' ').title()}"
    if kind == "score_component":
        return f"Score component: {value.replace('_', ' ').title()}"
    if kind == "agency":
        return value
    if kind == "clause":
        return value  # e.g. "FAR 52.204-21" — already canonical
    if kind == "cmmc":
        return f"CMMC {value}" if not value.lower().startswith("cmmc") else value
    if kind == "section":
        # Capitalize known section names
        upper = value.upper()
        if upper in ("L", "M"):
            return f"Section {upper}"
        if upper in ("SOW", "PWS", "SOO", "CDRL"):
            return upper
        return value
    if kind in ("sprs", "cui", "fci", "itar", "uei", "cage", "fcl"):
        return kind.upper()
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
