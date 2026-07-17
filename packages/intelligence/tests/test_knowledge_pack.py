"""Knowledge-pack loader tests."""

from __future__ import annotations

from mactech_intelligence.knowledge.pack import (
    LEGACY_EVIDENCE_CATEGORIES,
    load_pack,
    pack_version,
)


def test_pack_loads_all_families():
    pack = load_pack()
    families = {c.family for c in pack.concepts} | set(pack.blocks)
    for expected in (
        "cyber_services",
        "frcs_ot",
        "construction_systems",
        "clauses_frameworks",
        "acquisition_signals",
        "agency_offices",
        "disqualifiers",
        "pursuit_playbooks",
    ):
        assert expected in families, f"missing family {expected}"


def test_pack_version_is_stamped():
    v = pack_version()
    assert "frcs_ot=" in v and "cyber_services=" in v


def test_every_concept_has_required_fields():
    pack = load_pack()
    assert pack.concepts, "pack has no concepts"
    for c in pack.concepts:
        assert c.id and c.canonical_name and c.normalized_term
        assert c.family
        # match_patterns always begins with the canonical name.
        assert c.match_patterns[0] == c.canonical_name


def test_legacy_concepts_map_to_known_categories():
    pack = load_pack()
    legacy = [c for c in pack.concepts if c.evidence_category in LEGACY_EVIDENCE_CATEGORIES]
    # The relocated dictionary has 34 legacy-category concepts.
    assert len(legacy) == 34


def test_disqualifiers_carry_gate_codes():
    pack = load_pack()
    dqs = pack.disqualifiers
    assert dqs, "no disqualifiers loaded"
    for c in dqs:
        assert c.gate_code, f"disqualifier {c.id} missing gate_code"
        # Disqualifiers are NOT legacy detector categories (parity guard).
        assert c.evidence_category not in LEGACY_EVIDENCE_CATEGORIES


def test_pursuit_playbooks_cover_every_lane():
    playbooks = load_pack().block("pursuit_playbooks", "playbooks", {})
    for lane in (
        "PRIME_NOW",
        "PRIME_WITH_PARTNER",
        "SUB_TO_IDENTIFIED_PRIME",
        "SUB_TO_PRIME_NOT_YET_IDENTIFIED",
        "SHAPE_EARLY",
        "WATCH",
        "NO_BID",
    ):
        assert lane in playbooks, f"playbook missing lane {lane}"
        assert playbooks[lane], f"playbook {lane} is empty"
