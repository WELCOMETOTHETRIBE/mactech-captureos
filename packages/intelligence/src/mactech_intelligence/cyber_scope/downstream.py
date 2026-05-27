"""Prefill downstream capture artifacts from a CyberScopeAnalysis."""

from __future__ import annotations

from typing import Any

from mactech_intelligence.cyber_scope.schemas import CyberScopeAnalysis, DetectionResult


def _severity_for_signal(hit: DetectionResult, *, hidden: bool = False) -> str:
    if hidden:
        return "CRITICAL"
    tier = hit.ufgs_tier
    if tier == 1:
        return "CRITICAL"
    if tier in (2, 3, 4):
        return "HIGH"
    if hit.weight >= 25 or hit.confidence >= 0.9:
        return "HIGH"
    if hit.weight >= 10:
        return "MEDIUM"
    return "LOW"


def build_clause_risk_entries(analysis: CyberScopeAnalysis) -> list[dict[str, Any]]:
    """Turn detected signals into clause-risk log rows (deterministic)."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(
        *,
        category: str,
        reference: str,
        finding: str,
        evidence: str,
        severity: str,
        mitigation: str,
    ) -> None:
        key = f"{category}:{reference}:{finding[:80]}"
        if key in seen:
            return
        seen.add(key)
        entries.append(
            {
                "category": category,
                "reference": reference,
                "finding": finding,
                "evidence": evidence[:2000],
                "severity": severity,
                "mitigation": mitigation,
            }
        )

    for hit in analysis.hidden_scope_indicators:
        add(
            category="hidden_scope",
            reference=hit.normalized_term or hit.term,
            finding="Hidden OT/FRCS scope — title does not advertise cyber work.",
            evidence=hit.surrounding_text or hit.term,
            severity="CRITICAL",
            mitigation="Request CO/COR clarification; confirm UFGS 25 05 11 applicability before bid.",
        )

    for hit in analysis.top_signals[:12]:
        ref = hit.ufgs or hit.normalized_term or hit.term
        cat = hit.category or "signal"
        add(
            category=cat,
            reference=ref,
            finding=f"Detected {hit.term} ({cat}).",
            evidence=hit.surrounding_text or hit.term,
            severity=_severity_for_signal(hit),
            mitigation=_mitigation_for_category(cat, hit),
        )

    for req in analysis.missing_but_likely_requirements:
        add(
            category="missing_requirement",
            reference="Likely requirement",
            finding=req,
            evidence="",
            severity="MEDIUM",
            mitigation="Verify in Section C/L attachments; add to compliance matrix when confirmed.",
        )

    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    entries.sort(key=lambda e: order.get(e["severity"], 9))
    for i, e in enumerate(entries):
        e["sort_order"] = i
    return entries


def _mitigation_for_category(category: str, hit: DetectionResult) -> str:
    if category == "ufgs" or hit.ufgs:
        return "Map to MacTech FRCS/OT capability statement; confirm prime vs sub role."
    if category in ("rmf_ato_emass", "ufc_frcs"):
        return "Align ISSO/ISSM staffing; confirm eMASS/STIG path in proposal."
    if category == "far_dfars_cmmc":
        return "Flow down to subs; verify SPRS/CMMC in reps & certs."
    if category == "ot_ics_scada_pit":
        return "Document OT boundary; BACnet/UMCS segmentation in technical volume."
    return "Document in compliance matrix; assign owner for response."


def build_bid_no_bid_review(
    analysis: CyberScopeAnalysis,
    *,
    opportunity_title: str | None = None,
    agency: str | None = None,
) -> dict[str, Any]:
    """Structured bid/no-bid prefill — decision stays pending until human commits."""
    model = analysis.recommended_pursuit_model
    likelihood = analysis.overall_cyber_likelihood

    factors: list[dict[str, str]] = [
        {
            "factor": "Cyber scope score",
            "weight": "high",
            "note": f"{analysis.score}/100 — {likelihood} likelihood",
        },
        {
            "factor": "Pursuit model",
            "weight": "high",
            "note": model.replace("_", " ").title(),
        },
    ]
    if analysis.ufgs_tier_1_hit:
        factors.append(
            {
                "factor": "UFGS Tier 1",
                "weight": "high",
                "note": "25 05 11 / companion FRCS section detected",
            }
        )
    if analysis.ufgs_center_of_gravity:
        factors.append(
            {
                "factor": "Center of gravity",
                "weight": "high",
                "note": "25 05 11 + companion UFGS pattern",
            }
        )
    if analysis.hidden_scope_indicators:
        factors.append(
            {
                "factor": "Hidden scope",
                "weight": "urgent",
                "note": f"{len(analysis.hidden_scope_indicators)} hidden-scope indicator(s)",
            }
        )
    if analysis.missing_but_likely_requirements:
        factors.append(
            {
                "factor": "Gaps",
                "weight": "medium",
                "note": f"{len(analysis.missing_but_likely_requirements)} likely missing requirements",
            }
        )

    title_bit = opportunity_title or "This opportunity"
    agency_bit = f" ({agency})" if agency else ""
    rationale = (
        f"{title_bit}{agency_bit}\n\n"
        f"Cyber Scope Parser: {likelihood} / score {analysis.score}. "
        f"Recommended pursuit model: {model.replace('_', ' ')}.\n"
    )
    if analysis.ufgs_tier_1_hit:
        rationale += "\n• Tier 1 UFGS (FRCS bullseye) — align Patrick / Security pillar.\n"
    if analysis.hidden_scope_indicators:
        rationale += "\n• Hidden construction/facilities cyber scope — clarify FRCS/RMF boundaries before commit.\n"
    if model in ("FRCS_OT_SPECIALIST", "PRIME_PURSUE"):
        rationale += "\n• Strong fit for MacTech cyber/FRCS delivery — evaluate capacity and teaming.\n"
    elif model == "SUBCONTRACTOR_PURSUE":
        rationale += "\n• Prime scope likely construction/facilities — pursue as cyber/FRCS subcontractor.\n"
    elif model == "NO_ACTION":
        rationale += "\n• Low cyber signal — default no-bid unless strategic agency relationship.\n"
    else:
        rationale += "\n• Monitor amendments; formal bid/no-bid after attachment review.\n"

    recommended = "pending"
    if model == "NO_ACTION" and likelihood in ("NONE", "LOW"):
        recommended = "no_bid"

    return {
        "recommended_decision": recommended,
        "cyber_scope_summary": (
            f"{likelihood} cyber likelihood; score {analysis.score}; model {model}."
        ),
        "factors": factors,
        "rationale_draft": rationale.strip(),
        "pursuit_model": model,
        "likelihood": likelihood,
        "score": analysis.score,
    }


def build_proposal_outline(
    analysis: CyberScopeAnalysis,
    *,
    opportunity_title: str | None = None,
) -> dict[str, Any]:
    """Section skeleton for a cyber-heavy technical volume."""
    title = opportunity_title or "Opportunity"
    sections: list[dict[str, Any]] = [
        {
            "id": "exec",
            "heading": "Executive summary — cyber scope",
            "bullets": [
                f"Overall cyber likelihood: {analysis.overall_cyber_likelihood} (score {analysis.score}).",
                f"Recommended capture posture: {analysis.recommended_pursuit_model.replace('_', ' ')}.",
            ],
        },
        {
            "id": "frcs",
            "heading": "FRCS / facility-related control systems",
            "bullets": _outline_bullets(analysis, ("ufc_frcs", "ufgs"), limit=6),
        },
        {
            "id": "rmf",
            "heading": "RMF, ATO, and eMASS",
            "bullets": _outline_bullets(analysis, ("rmf_ato_emass",), limit=5),
        },
        {
            "id": "ot",
            "heading": "OT / ICS / building automation",
            "bullets": _outline_bullets(analysis, ("ot_ics_scada_pit",), limit=5),
        },
    ]
    if analysis.hidden_scope_indicators:
        sections.append(
            {
                "id": "hidden",
                "heading": "Hidden scope and clarifications",
                "bullets": [
                    f"{h.term}: {h.surrounding_text[:200]}"
                    for h in analysis.hidden_scope_indicators[:4]
                ],
            }
        )
    if analysis.missing_but_likely_requirements:
        sections.append(
            {
                "id": "gaps",
                "heading": "Likely requirements to confirm",
                "bullets": list(analysis.missing_but_likely_requirements[:8]),
            }
        )
    sections.append(
        {
            "id": "team",
            "heading": "Teaming and compliance",
            "bullets": [
                "CMMC / DFARS flow-down to subcontractors (if prime).",
                "ISSO/ISSM and RMF artifact ownership.",
                f"Capture strategy aligned to {analysis.recommended_pursuit_model.replace('_', ' ')}.",
            ],
        }
    )
    return {
        "title": f"Cyber technical outline — {title[:120]}",
        "sections": sections,
    }


def _outline_bullets(
    analysis: CyberScopeAnalysis,
    keys: tuple[str, ...],
    *,
    limit: int,
) -> list[str]:
    bullets: list[str] = []
    cats = analysis.detected_categories
    for key in keys:
        hits = getattr(cats, key, []) if hasattr(cats, key) else []
        for h in hits[:limit]:
            label = h.ufgs or h.normalized_term or h.term
            bullets.append(f"{label}: {h.surrounding_text[:160] or h.term}")
        if len(bullets) >= limit:
            break
    if not bullets and analysis.top_signals:
        for s in analysis.top_signals[:limit]:
            bullets.append(f"{s.term} ({s.category})")
    return bullets[:limit] or ["No explicit signals — confirm in solicitation attachments."]
