"""UFGS 8-tier section matcher."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from mactech_intelligence.cyber_scope.regex_utils import (
    compile_literal_patterns,
    surrounding_text,
)
from mactech_intelligence.cyber_scope.schemas import DetectionResult

_REPO_ROOT = Path(__file__).resolve().parents[5]
_UFGS_YAML = _REPO_ROOT / "data" / "cyber_scope_ufgs_tiers.yml"


@dataclass(frozen=True)
class UfgsSectionDef:
    ufgs: str
    title: str
    tier: int
    weight: int
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class UfgsTierConfig:
    tier_multipliers: dict[int, float]
    center_of_gravity_companions: tuple[str, ...]
    sections: tuple[UfgsSectionDef, ...]


@lru_cache(maxsize=1)
def load_ufgs_config(path: Path | None = None) -> UfgsTierConfig:
    yaml_path = path or _UFGS_YAML
    raw: dict[str, Any] = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    sections = tuple(
        UfgsSectionDef(
            ufgs=s["ufgs"],
            title=s["title"],
            tier=int(s["tier"]),
            weight=int(s.get("weight", 10)),
            aliases=tuple(s.get("aliases", [])),
        )
        for s in raw.get("sections", [])
    )
    return UfgsTierConfig(
        tier_multipliers={int(k): float(v) for k, v in raw.get("tier_multipliers", {}).items()},
        center_of_gravity_companions=tuple(raw.get("center_of_gravity_companions", [])),
        sections=sections,
    )


def _patterns_for_section(section: UfgsSectionDef) -> list[str]:
    patterns = [f"UFGS {section.ufgs}", section.ufgs, *section.aliases]
    return list(dict.fromkeys(patterns))


def match_ufgs_sections(text: str, config: UfgsTierConfig | None = None) -> list[DetectionResult]:
    cfg = config or load_ufgs_config()
    hits: list[DetectionResult] = []
    for section in cfg.sections:
        compiled = compile_literal_patterns(_patterns_for_section(section))
        for pat in compiled:
            for m in pat.finditer(text):
                mult = cfg.tier_multipliers.get(section.tier, 0.5)
                effective_weight = int(section.weight * mult)
                hits.append(
                    DetectionResult(
                        term=f"UFGS {section.ufgs}",
                        normalized_term=section.ufgs,
                        category="ufgs",
                        confidence=1.0,
                        weight=effective_weight,
                        match_type="EXACT",
                        surrounding_text=surrounding_text(text, m.start(), m.end()),
                        ufgs=section.ufgs,
                        ufgs_tier=section.tier,
                    )
                )
                break
            else:
                continue
            break
    return hits


def group_ufgs_by_tier(hits: list[DetectionResult]) -> dict[str, list[DetectionResult]]:
    grouped: dict[str, list[DetectionResult]] = {str(i): [] for i in range(1, 9)}
    for h in hits:
        if h.ufgs_tier is not None:
            grouped[str(h.ufgs_tier)].append(h)
    return {k: v for k, v in grouped.items() if v}


def check_center_of_gravity(
    hits: list[DetectionResult], config: UfgsTierConfig | None = None
) -> bool:
    cfg = config or load_ufgs_config()
    found = {h.normalized_term for h in hits if h.ufgs}
    has_bullseye = "25 05 11" in found
    if not has_bullseye:
        return False
    companions = set(cfg.center_of_gravity_companions)
    return bool(found & companions)
