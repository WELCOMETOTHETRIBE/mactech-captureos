"""LLM summaries and email drafts for cyber scope analyses."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from mactech_intelligence.cyber_scope.schemas import CyberScopeAnalysis, SuggestedAction
from mactech_intelligence.llm import AnthropicLLMClient, LLMResponse

PROMPT_SUMMARY = Path(__file__).parent.parent / "prompts" / "cyber_scope_summary.md"
PROMPT_CLARIFICATION = Path(__file__).parent.parent / "prompts" / "cyber_scope_clarification_email.md"
PROMPT_PRIME = Path(__file__).parent.parent / "prompts" / "cyber_scope_prime_outreach.md"

SUMMARY_VERSION = "v1"
CLARIFICATION_VERSION = "v1"
PRIME_VERSION = "v1"

SYSTEM_MARKER = "---SYSTEM---"
USER_MARKER = "---USER---"


@dataclass(frozen=True)
class CyberScopeOppContext:
    title: str
    agency: str | None = None
    solicitation_number: str | None = None
    notice_type: str | None = None
    response_deadline: str | None = None


def _load_prompt(path: Path) -> tuple[str, str]:
    raw = path.read_text()
    if SYSTEM_MARKER not in raw or USER_MARKER not in raw:
        raise RuntimeError(f"prompt file {path} missing required markers")
    _, rest = raw.split(SYSTEM_MARKER, 1)
    system, user = rest.split(USER_MARKER, 1)
    system_clean = "\n".join(
        line for line in system.strip().splitlines() if not line.startswith("#")
    )
    user_clean = "\n".join(
        line for line in user.strip().splitlines() if not line.startswith("#")
    )
    return system_clean, user_clean


def _signals_block(signals: list, *, limit: int = 8) -> str:
    if not signals:
        return "  (none)"
    lines: list[str] = []
    for s in signals[:limit]:
        term = getattr(s, "term", None) or s.get("term", "")
        cat = getattr(s, "category", None) or s.get("category", "")
        text = getattr(s, "surrounding_text", None) or s.get("surrounding_text", "")
        lines.append(f"  - {term} ({cat}): {(text or '')[:200]}")
    return "\n".join(lines)


def _actions_block(actions: list[SuggestedAction] | list[dict]) -> str:
    if not actions:
        return "  (none)"
    lines: list[str] = []
    for a in actions[:6]:
        if isinstance(a, SuggestedAction):
            lines.append(f"  - {a.title}: {a.rationale}")
        else:
            lines.append(f"  - {a.get('title', '')}: {a.get('rationale', '')}")
    return "\n".join(lines)


def _missing_block(missing: list[str]) -> str:
    if not missing:
        return "  (none)"
    return "\n".join(f"  - {m}" for m in missing[:8])


def deterministic_summary(
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> str:
    """Template summary when LLM is unavailable."""
    title = opp.title or "This opportunity"
    posture = analysis.recommended_pursuit_model.replace("_", " ").lower()
    lines = [
        f"Bottom line: {title} — {analysis.overall_cyber_likelihood} cyber likelihood "
        f"(score {analysis.score}); recommended posture: {posture}.",
        "",
        "Key signals:",
    ]
    for s in analysis.top_signals[:4]:
        lines.append(f"• {s.term} ({s.category})")
    if analysis.hidden_scope_indicators:
        lines.append(
            f"• Hidden scope: {analysis.hidden_scope_indicators[0].term} — "
            "confirm FRCS/RMF applicability with CO/COR before commit."
        )
    if analysis.missing_but_likely_requirements:
        lines.append(
            f"• Gap to verify: {analysis.missing_but_likely_requirements[0]}"
        )
    return "\n".join(lines)


def _parse_json_email(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    return {
        "subject": str(data.get("subject", "")).strip(),
        "body": str(data.get("body", "")).strip(),
    }


def deterministic_clarification_email(
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> dict[str, str]:
    sol = opp.solicitation_number or "[SOLICITATION NUMBER]"
    hidden = (
        analysis.hidden_scope_indicators[0].term
        if analysis.hidden_scope_indicators
        else "facility-related control systems"
    )
    return {
        "subject": f"Clarification request — FRCS/UFGS scope ({sol})",
        "body": (
            f"Dear [CO NAME],\n\n"
            f"MacTech Solutions LLC is evaluating {opp.title} ({sol}). "
            f"Our review identified references to {hidden} and related "
            f"UFGS/FRCS requirements that are not explicit in the notice title.\n\n"
            "Please confirm:\n"
            "1. Whether UFGS 25 05 11 (or equivalent FRCS cyber section) applies to this effort.\n"
            "2. Whether the Government expects RMF/ATO artifacts (SSP, SAR, eMASS) as deliverables.\n"
            "3. Whether OT/building automation (BACnet/UMCS) boundaries are in scope for the prime.\n\n"
            "Thank you for your guidance.\n\n"
            "Respectfully,\n"
            "[Your name]\n"
            "MacTech Solutions LLC"
        ),
    }


def deterministic_prime_outreach(
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> dict[str, str]:
    sol = opp.solicitation_number or "[SOLICITATION NUMBER]"
    return {
        "subject": f"SDVOSB cyber/FRCS subcontract support — {sol}",
        "body": (
            f"Dear [CONTACT NAME] at [PRIME COMPANY],\n\n"
            f"MacTech Solutions LLC (SDVOSB) specializes in UFGS 25 05 11 / FRCS, "
            f"RMF/ATO, and OT/ICS integration for federal construction and facilities work.\n\n"
            f"We reviewed {opp.title} ({sol}) and see embedded cyber scope "
            f"({analysis.overall_cyber_likelihood}, score {analysis.score}). "
            f"If you are pursuing as prime, we can support FRCS documentation, "
            f"RMF artifacts, and commissioning cyber deliverables.\n\n"
            "Open to a 15-minute call this week.\n\n"
            "Regards,\n"
            "[Your name]\n"
            "MacTech Solutions LLC"
        ),
    }


def build_governance_handoff_stub(
    *,
    analysis_id: str,
    opportunity_id: str,
    analysis: CyberScopeAnalysis,
) -> dict:
    """GovernanceOS Readiness Facts handoff — stub until hub is live."""
    return {
        "status": "stub",
        "integration": "GovernanceOS",
        "message": "Export bundle placeholder. Wire to GovernanceOS Readiness Facts API in Phase 4.",
        "analysis_id": analysis_id,
        "opportunity_id": opportunity_id,
        "requested_checks": [
            "cmmc_level_2_alignment",
            "sprs_score_current",
            "facility_clearance_if_pds",
            "representations_and_certs",
            "teaming_agreements_status",
        ],
        "cyber_likelihood": analysis.overall_cyber_likelihood,
        "pursuit_model": analysis.recommended_pursuit_model,
        "generated_at": datetime.now(UTC).isoformat(),
    }


def build_pricing_handoff_stub(
    *,
    analysis_id: str,
    opportunity_id: str,
    analysis: CyberScopeAnalysis,
) -> dict:
    """PricingOS labor-rate / basis-of-estimate stub."""
    return {
        "status": "stub",
        "integration": "PricingOS",
        "message": "Pricing handoff placeholder. Map UFGS tiers to labor categories when PricingOS connects.",
        "analysis_id": analysis_id,
        "opportunity_id": opportunity_id,
        "suggested_labor_categories": [
            "ISSO",
            "ISSM",
            "FRCS_OT_ENGINEER",
            "RMF_SECURITY_ANALYST",
            "COMMISSIONING_CYBER_REVIEWER",
        ],
        "ufgs_center_of_gravity": analysis.ufgs_center_of_gravity,
        "score": analysis.score,
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def generate_cyber_scope_summary(
    client: AnthropicLLMClient,
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> LLMResponse:
    system_template, user_template = _load_prompt(PROMPT_SUMMARY)
    user = user_template.format(
        title=opp.title,
        agency=opp.agency or "(not specified)",
        solicitation_number=opp.solicitation_number or "(not specified)",
        response_deadline=opp.response_deadline or "(not specified)",
        score=analysis.score,
        likelihood=analysis.overall_cyber_likelihood,
        pursuit_model=analysis.recommended_pursuit_model,
        center_of_gravity="yes" if analysis.ufgs_center_of_gravity else "no",
        tier_1_hit="yes" if analysis.ufgs_tier_1_hit else "no",
        scan_pass=analysis.scan_pass,
        top_signals_block=_signals_block(analysis.top_signals),
        hidden_scope_block=_signals_block(analysis.hidden_scope_indicators),
        missing_block=_missing_block(analysis.missing_but_likely_requirements),
        actions_block=_actions_block(analysis.suggested_actions),
    )
    return await client.complete(
        system=system_template,
        user=user,
        complexity="smart",
        max_tokens=500,
        purpose=f"cyber_scope_summary:{SUMMARY_VERSION}",
    )


async def generate_clarification_email(
    client: AnthropicLLMClient,
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> tuple[dict[str, str], LLMResponse]:
    system_template, user_template = _load_prompt(PROMPT_CLARIFICATION)
    user = user_template.format(
        title=opp.title,
        agency=opp.agency or "(not specified)",
        solicitation_number=opp.solicitation_number or "(not specified)",
        notice_type=opp.notice_type or "(not specified)",
        likelihood=analysis.overall_cyber_likelihood,
        score=analysis.score,
        hidden_scope_block=_signals_block(analysis.hidden_scope_indicators),
        top_signals_block=_signals_block(analysis.top_signals),
        missing_block=_missing_block(analysis.missing_but_likely_requirements),
    )
    resp = await client.complete(
        system=system_template,
        user=user,
        complexity="smart",
        max_tokens=700,
        purpose=f"cyber_scope_clarification:{CLARIFICATION_VERSION}",
    )
    try:
        email = _parse_json_email(resp.text)
    except (json.JSONDecodeError, KeyError):
        email = deterministic_clarification_email(analysis, opp)
    return email, resp


async def generate_prime_outreach_email(
    client: AnthropicLLMClient,
    analysis: CyberScopeAnalysis,
    opp: CyberScopeOppContext,
) -> tuple[dict[str, str], LLMResponse]:
    system_template, user_template = _load_prompt(PROMPT_PRIME)
    user = user_template.format(
        title=opp.title,
        agency=opp.agency or "(not specified)",
        solicitation_number=opp.solicitation_number or "(not specified)",
        response_deadline=opp.response_deadline or "(not specified)",
        pursuit_model=analysis.recommended_pursuit_model,
        likelihood=analysis.overall_cyber_likelihood,
        score=analysis.score,
        top_signals_block=_signals_block(analysis.top_signals),
    )
    resp = await client.complete(
        system=system_template,
        user=user,
        complexity="smart",
        max_tokens=600,
        purpose=f"cyber_scope_prime_outreach:{PRIME_VERSION}",
    )
    try:
        email = _parse_json_email(resp.text)
    except (json.JSONDecodeError, KeyError):
        email = deterministic_prime_outreach(analysis, opp)
    return email, resp
