"""Load general cyber scope dictionary terms."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DICT_YAML = _REPO_ROOT / "data" / "cyber_scope_dictionary.yml"


@dataclass(frozen=True)
class DictionaryTerm:
    category: str
    term: str
    normalized_term: str
    weight: int
    aliases: tuple[str, ...]
    regex: str | None = None


@lru_cache(maxsize=1)
def load_dictionary(path: Path | None = None) -> tuple[DictionaryTerm, ...]:
    yaml_path = path or _DICT_YAML
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    terms = []
    for t in raw.get("terms", []):
        terms.append(
            DictionaryTerm(
                category=t["category"],
                term=t["term"],
                normalized_term=t.get("normalized_term", t["term"]),
                weight=int(t.get("weight", 10)),
                aliases=tuple(t.get("aliases", [])),
                regex=t.get("regex"),
            )
        )
    return tuple(terms)


@lru_cache(maxsize=1)
def load_construction_signals(path: Path | None = None) -> tuple[str, ...]:
    yaml_path = path or _DICT_YAML
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return tuple(raw.get("construction_signals", []))
