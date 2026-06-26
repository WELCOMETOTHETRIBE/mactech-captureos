"""Unit tests for the SBIR Submission Engine's pure-logic layer.

Covers:
  * Prompt MD ships with the package and loads.
  * Phase user-message builders produce the right anchor tokens.
  * Depth gating constants are consistent with the engine spec.
"""

from __future__ import annotations

from mactech_intelligence.sbir_phases import (
    SCAFFOLD_VOLUME_KEYS,
    VOLUME_SPECS,
    build_consistency_user_message,
    build_intake_user_message,
    build_overclaim_user_message,
    build_preflight_user_message,
    build_strategy_user_message,
    build_synergy_user_message,
    build_topic_extract_user_message,
    build_volume_user_message,
)
from mactech_intelligence.sbir_submission_engine import (
    PROMPT_PATH,
    PROMPT_VERSION,
)


def test_prompt_md_ships_with_package() -> None:
    assert PROMPT_PATH.is_file()
    body = PROMPT_PATH.read_text(encoding="utf-8")
    assert "SBIR Submission Engine" in body
    assert "CRITICAL RULES" in body
    assert "CONSTANTS" in body
    # The CMMC L2/L3 framing rule is a critical guardrail.
    assert "CMMC L2" in body and "CMMC L3" in body


def test_prompt_version_is_set() -> None:
    assert PROMPT_VERSION == "v1"


def test_intake_message_demands_verdict_line() -> None:
    msg = build_intake_user_message("Topic: NV007\nDepth: scaffold")
    assert "VALIDATION_OK" in msg
    assert "HALT:" in msg
    assert "PHASE 0" in msg
    assert "NV007" in msg


def test_topic_extract_message_carries_payload() -> None:
    msg = build_topic_extract_user_message(
        input_summary="Topic: NV007",
        topic_payload="TOPIC PDF TEXT HERE",
    )
    assert "PHASE 1" in msg
    assert "topic-extract.md" in msg
    assert "TOPIC PDF TEXT HERE" in msg
    assert "⚠️ VERIFY:" in msg


def test_synergy_message_includes_hypothesis_and_extract() -> None:
    msg = build_synergy_user_message(
        input_summary="x",
        topic_extract="TOPIC FACTS",
        synergy_hypothesis="HYPOTHESIS",
    )
    assert "PHASE 2" in msg
    assert "synergy-assessment.md" in msg
    assert "HYPOTHESIS" in msg
    assert "TOPIC FACTS" in msg


def test_strategy_message_demands_python_verification() -> None:
    msg = build_strategy_user_message("x", "TE", "SA")
    assert "PHASE 3" in msg
    assert "strategy.md" in msg
    assert "Python" in msg
    assert "POW" in msg


def test_overclaim_message_lists_inputs() -> None:
    msg = build_overclaim_user_message("x", "TE", "SA", "STR")
    assert "PHASE 4" in msg
    assert "overclaim-audit.md" in msg
    assert "STR" in msg


def test_consistency_message_carries_files() -> None:
    msg = build_consistency_user_message("### volume-2-technical.md\n\nbody")
    assert "PHASE 6" in msg
    assert "inconsistency-report.md" in msg
    assert "volume-2-technical.md" in msg


def test_preflight_message_inlines_verify_flags() -> None:
    msg = build_preflight_user_message("x", ["⚠️ VERIFY: PI commitment"])
    assert "PHASE 7" in msg
    assert "preflight.md" in msg
    assert "⚠️ VERIFY: PI commitment" in msg


def test_volume_specs_cover_required_files() -> None:
    paths = {spec.relpath for spec in VOLUME_SPECS}
    # Spot-check the artifacts the engine spec promises.
    for expected in [
        "volume-1-cover-sheet.md",
        "dsip-cheat-sheet.md",
        "volume-2-technical.md",
        "volume-3-cost.md",
        "volume-4-commercialization-report.md",
        "volume-5-supporting/README.md",
        "volume-5-supporting/01-pi-cv.md",
        "volume-5-supporting/02-bibliography.md",
        "volume-6-fwa.md",
        "volume-7-foreign-disclosures.md",
        "email-to-brian.md",
        "README.md",
    ]:
        assert expected in paths, f"missing volume spec for {expected}"


def test_scaffold_subset_matches_spec() -> None:
    # Scaffold depth ships only Vol 1 + DSIP cheat sheet per engine spec.
    assert {"volume_1", "dsip_cheat_sheet"} == SCAFFOLD_VOLUME_KEYS


def test_volume_user_message_includes_brief_and_context() -> None:
    spec = next(s for s in VOLUME_SPECS if s.key == "volume_1")
    msg = build_volume_user_message(spec, "INPUTS\nfoo")
    assert "PHASE 5" in msg
    assert "VOLUME 1" in msg
    assert "INPUTS" in msg
