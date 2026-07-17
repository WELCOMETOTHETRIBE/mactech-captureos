"""Regression guard: the pack-backed dictionary adapter must reproduce the
legacy data/cyber_scope_dictionary.yml exactly, so the cyber_scope detector is
byte-for-byte unchanged by Slice 1.
"""

from __future__ import annotations

from mactech_intelligence.cyber_scope.dictionary import (
    _DICT_YAML,
    _from_yaml,
    load_construction_signals,
    load_dictionary,
)


def _key(t):
    return (t.category, t.term, t.normalized_term, t.weight, t.regex, frozenset(t.aliases))


def test_pack_dictionary_matches_legacy_yaml():
    pack_terms = load_dictionary()  # pack-backed
    yaml_terms = _from_yaml(_DICT_YAML)  # legacy reference
    assert {_key(t) for t in pack_terms} == {_key(t) for t in yaml_terms}
    assert len(pack_terms) == len(yaml_terms)


def test_construction_signals_match_legacy():
    import yaml

    legacy = tuple(yaml.safe_load(_DICT_YAML.read_text(encoding="utf-8"))["construction_signals"])
    assert load_construction_signals() == legacy


def test_explicit_path_still_loads_legacy_file():
    # Tooling that passes an explicit path keeps the original file behavior.
    terms = load_dictionary(_DICT_YAML)
    assert {_key(t) for t in terms} == {_key(t) for t in _from_yaml(_DICT_YAML)}
