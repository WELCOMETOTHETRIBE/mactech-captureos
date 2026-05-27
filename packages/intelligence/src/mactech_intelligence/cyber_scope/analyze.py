"""Orchestrate cyber scope analysis."""

from __future__ import annotations

from mactech_intelligence.cyber_scope.actions import (
    generate_search_queries,
    generate_suggested_actions,
)
from mactech_intelligence.cyber_scope.hidden_scope import detect_hidden_scope
from mactech_intelligence.cyber_scope.matcher import run_dictionary_matching
from mactech_intelligence.cyber_scope.normalize import normalize_contract_text
from mactech_intelligence.cyber_scope.schemas import CyberScopeAnalysis, DetectedCategories
from mactech_intelligence.cyber_scope.scorer import (
    PARSER_VERSION,
    build_top_signals,
    compute_score,
    missing_likely_requirements,
    recommend_pursuit_model,
    _likelihood_from_score,
)
from mactech_intelligence.cyber_scope.sources import CyberScopeTextSource
from mactech_intelligence.cyber_scope.ufgs_tiers import (
    check_center_of_gravity,
    group_ufgs_by_tier,
    match_ufgs_sections,
)


def analyze_cyber_scope(source: CyberScopeTextSource) -> CyberScopeAnalysis:
    raw = source.combined_text
    text = normalize_contract_text(raw)
    dict_hits = run_dictionary_matching(text)
    ufgs_hits = match_ufgs_sections(text)
    ufgs_by_tier = group_ufgs_by_tier(ufgs_hits)
    hidden = detect_hidden_scope(
        title=source.title,
        text=text,
        ufgs_hits=ufgs_hits,
        dict_hits=dict_hits,
    )
    center = check_center_of_gravity(ufgs_hits)

    categories = DetectedCategories(
        ufc_frcs=dict_hits.get("ufc_frcs", []),
        ufgs=ufgs_hits,
        ufgs_by_tier=ufgs_by_tier,
        rmf_ato_emass=dict_hits.get("rmf_ato_emass", []),
        nist_cnssi_fips=dict_hits.get("nist_cnssi_fips", []),
        ot_ics_scada_pit=dict_hits.get("ot_ics_scada_pit", []),
        branch_specific=dict_hits.get("branch_specific", []),
        contract_location_triggers=dict_hits.get("contract_location_triggers", []),
        far_dfars_cmmc=dict_hits.get("far_dfars_cmmc", []),
    )

    score = compute_score(
        dict_hits=dict_hits,
        ufgs_hits=ufgs_hits,
        hidden_indicators=hidden,
        center_of_gravity=center,
        title=source.title,
    )
    likelihood = _likelihood_from_score(score)

    all_hits: list = []
    for lst in (
        categories.ufc_frcs,
        categories.ufgs,
        categories.rmf_ato_emass,
        categories.nist_cnssi_fips,
        categories.ot_ics_scada_pit,
        categories.branch_specific,
        categories.far_dfars_cmmc,
    ):
        all_hits.extend(lst)

    draft = CyberScopeAnalysis(
        overall_cyber_likelihood=likelihood,
        recommended_pursuit_model="WATCHLIST",
        score=score,
        detected_categories=categories,
        top_signals=build_top_signals(all_hits),
        hidden_scope_indicators=hidden,
        ufgs_center_of_gravity=center,
        ufgs_tier_1_hit=any(h.ufgs_tier == 1 for h in ufgs_hits),
        top_ufgs_sections=list(
            dict.fromkeys(h.normalized_term for h in ufgs_hits if h.ufgs)
        )[:8],
        scan_pass=source.scan_pass,
        parser_version=PARSER_VERSION,
        metadata=dict(source.metadata),
    )
    draft.recommended_pursuit_model = recommend_pursuit_model(draft, title=source.title)
    draft.missing_but_likely_requirements = missing_likely_requirements(draft)
    draft.suggested_actions = generate_suggested_actions(draft)
    draft.evidence_snippets = build_top_signals(all_hits + hidden, limit=20)
    draft.metadata["search_queries"] = generate_search_queries(draft)
    return draft
