"""CSV and PDF export helpers for cyber scope feed and analyses."""

from __future__ import annotations

import csv
import io
from typing import Any


def feed_rows_to_csv(rows: list[dict[str, Any]]) -> str:
    """Build CSV string from feed export row dicts."""
    if not rows:
        return (
            "analysis_id,opportunity_id,title,agency,solicitation_number,"
            "likelihood,pursuit_model,score,ufgs_center_of_gravity,ufgs_tier_1_hit,"
            "top_ufgs_sections,scan_pass,response_deadline,updated_at\n"
        )
    buf = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def analysis_to_pdf_bytes(
    *,
    title: str,
    agency: str | None,
    solicitation_number: str | None,
    analysis_summary: str | None,
    likelihood: str,
    pursuit_model: str,
    score: int,
    top_signals: list[dict[str, Any]],
    hidden_scope: list[dict[str, Any]],
    missing: list[str],
    clarification_email: dict[str, str] | None = None,
) -> bytes:
    """Render a simple text PDF via PyMuPDF."""
    import fitz  # type: ignore[import-untyped]

    lines: list[str] = [
        "MacTech CaptureOS — Cyber Scope Analysis",
        "=" * 50,
        f"Title: {title}",
        f"Agency: {agency or '—'}",
        f"Solicitation: {solicitation_number or '—'}",
        f"Score: {score} · Likelihood: {likelihood} · Model: {pursuit_model}",
        "",
    ]
    if analysis_summary:
        lines.extend(["Executive summary", "-" * 40, analysis_summary, ""])
    lines.extend(["Top signals", "-" * 40])
    for s in top_signals[:12]:
        term = s.get("term", "")
        cat = s.get("category", "")
        ev = (s.get("surrounding_text") or "")[:300]
        lines.append(f"• {term} ({cat})")
        if ev:
            lines.append(f"  {ev}")
    if hidden_scope:
        lines.extend(["", "Hidden scope", "-" * 40])
        for h in hidden_scope[:6]:
            lines.append(f"• {h.get('term', '')}: {(h.get('surrounding_text') or '')[:200]}")
    if missing:
        lines.extend(["", "Missing but likely", "-" * 40])
        for m in missing[:8]:
            lines.append(f"• {m}")
    if clarification_email:
        lines.extend(
            [
                "",
                "Clarification email draft",
                "-" * 40,
                f"Subject: {clarification_email.get('subject', '')}",
                "",
                clarification_email.get("body", ""),
            ]
        )

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 50
    line_height = 13
    margin = 50
    max_y = 742
    for line in lines:
        if y > max_y:
            page = doc.new_page(width=612, height=792)
            y = 50
        page.insert_text((margin, y), line, fontsize=10)
        y += line_height
    pdf_bytes: bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
