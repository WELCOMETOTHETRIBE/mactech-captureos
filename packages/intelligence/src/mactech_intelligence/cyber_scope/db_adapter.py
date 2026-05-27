"""Convert persisted cyber scope JSON columns to CyberScopeAnalysis schema."""

from __future__ import annotations

from typing import Any

from mactech_intelligence.cyber_scope.schemas import (
    CyberScopeAnalysis,
    DetectedCategories,
    DetectionResult,
    SuggestedAction,
)


def schema_from_persisted(
    *,
    overall_cyber_likelihood: str,
    recommended_pursuit_model: str,
    score: int,
    detected_categories_json: dict[str, Any],
    top_signals_json: list[Any],
    hidden_scope_indicators_json: list[Any],
    missing_requirements_json: list[str],
    suggested_actions_json: list[Any],
    evidence_snippets_json: list[Any],
    ufgs_center_of_gravity: bool,
    ufgs_tier_1_hit: bool,
    scan_pass: str,
    parser_version: str,
    metadata_json: dict[str, Any] | None = None,
) -> CyberScopeAnalysis:
    cats_raw = detected_categories_json or {}
    ufgs_by_tier = {
        k: [DetectionResult.model_validate(x) for x in v]
        for k, v in (cats_raw.get("ufgs_by_tier") or {}).items()
    }
    categories = DetectedCategories(
        ufc_frcs=[DetectionResult.model_validate(x) for x in cats_raw.get("ufc_frcs", [])],
        ufgs=[DetectionResult.model_validate(x) for x in cats_raw.get("ufgs", [])],
        ufgs_by_tier=ufgs_by_tier,
        rmf_ato_emass=[
            DetectionResult.model_validate(x) for x in cats_raw.get("rmf_ato_emass", [])
        ],
        nist_cnssi_fips=[
            DetectionResult.model_validate(x) for x in cats_raw.get("nist_cnssi_fips", [])
        ],
        ot_ics_scada_pit=[
            DetectionResult.model_validate(x) for x in cats_raw.get("ot_ics_scada_pit", [])
        ],
        branch_specific=[
            DetectionResult.model_validate(x) for x in cats_raw.get("branch_specific", [])
        ],
        contract_location_triggers=[
            DetectionResult.model_validate(x)
            for x in cats_raw.get("contract_location_triggers", [])
        ],
        far_dfars_cmmc=[
            DetectionResult.model_validate(x) for x in cats_raw.get("far_dfars_cmmc", [])
        ],
    )
    return CyberScopeAnalysis(
        overall_cyber_likelihood=overall_cyber_likelihood,  # type: ignore[arg-type]
        recommended_pursuit_model=recommended_pursuit_model,  # type: ignore[arg-type]
        score=score,
        detected_categories=categories,
        top_signals=[DetectionResult.model_validate(x) for x in (top_signals_json or [])],
        hidden_scope_indicators=[
            DetectionResult.model_validate(x)
            for x in (hidden_scope_indicators_json or [])
        ],
        missing_but_likely_requirements=missing_requirements_json or [],
        suggested_actions=[
            SuggestedAction.model_validate(x) for x in (suggested_actions_json or [])
        ],
        evidence_snippets=[
            DetectionResult.model_validate(x) for x in (evidence_snippets_json or [])
        ],
        ufgs_center_of_gravity=ufgs_center_of_gravity,
        ufgs_tier_1_hit=ufgs_tier_1_hit,
        parser_version=parser_version,
        scan_pass=scan_pass,  # type: ignore[arg-type]
        metadata=metadata_json or {},
    )
