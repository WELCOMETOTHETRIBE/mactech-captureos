"""Shared regex compilation for cyber scope and clause detection."""

from __future__ import annotations

import re


def compile_literal_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    """Treat patterns as literal phrases with flexible whitespace."""
    out: list[re.Pattern[str]] = []
    for p in patterns:
        escaped = re.escape(p.strip())
        flexible = re.sub(r"\\\s+", r"\\s+", escaped)
        anchored = rf"(?<![A-Za-z0-9]){flexible}(?![A-Za-z0-9])"
        out.append(re.compile(anchored, re.IGNORECASE))
    return out


def compile_regex_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def surrounding_text(text: str, start: int, end: int, window: int = 120) -> str:
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    snippet = text[lo:hi].replace("\n", " ")
    return snippet.strip()
