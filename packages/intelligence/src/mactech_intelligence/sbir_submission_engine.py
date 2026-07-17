"""SBIR Submission Engine — multi-phase agent that turns a topic + user
context into a complete Phase I submission package.

System prompt: docs/prompts/sbir-submission-engine.md (mirrored into
packages/intelligence/.../prompts/ at install time).

Streaming model: yields `SBIREvent` items the API route can serialize as
SSE. Events:

    phase_start   { phase, label }
    delta         { phase, text }
    file_written  { phase, path, bytes }
    phase_complete{ phase, duration_ms }
    error         { message }
    final         { submission_id (set by caller), output_dir,
                    file_count, verify_flags, model,
                    input_tokens, output_tokens }

Each phase is one Sonnet-4.6 streaming call. The system prompt is the
master engine spec verbatim; the user message is built by
`sbir_phases.build_*_user_message()`.

`run_sbir_submission()` is depth-aware:
    scaffold  -> phase 0, 1, 5 (only Vol 1 + DSIP cheat sheet)
    standard  -> phase 0..7, markdown only
    complete  -> standard + PDF/Excel/DOCX renders (DEFERRED — engine
                 finishes the markdown bundle and surfaces a
                 `complete_rendering_deferred` warning in verify_flags
                 so the UI can show why no PDF/Excel/DOCX appeared)
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mactech_intelligence.llm import AnthropicLLMClient
from mactech_intelligence.sbir_phases import (
    SCAFFOLD_VOLUME_KEYS,
    VOLUME_SPECS,
    VolumeSpec,
    build_consistency_user_message,
    build_intake_user_message,
    build_overclaim_user_message,
    build_preflight_user_message,
    build_strategy_user_message,
    build_synergy_user_message,
    build_topic_extract_user_message,
    build_volume_user_message,
)

PROMPT_PATH = Path(__file__).parent / "prompts" / "sbir-submission-engine.md"
PROMPT_VERSION = "v1"

# Reasonable per-phase ceilings. The longest single phase is Vol 2; allow
# 8000 tokens for that. Other phases cap lower to keep stalls visible.
DEFAULT_MAX_TOKENS_SHORT = 4000
DEFAULT_MAX_TOKENS_LONG = 8000

Depth = Literal["scaffold", "standard", "complete"]

_VERIFY_RE = re.compile(r"⚠️ VERIFY:[^\n\r]+")


@dataclass(frozen=True)
class SBIRAttachment:
    """An attachment provided by the user — already decoded to text.

    The API route is responsible for decoding PDFs (via pymupdf) and
    text-shaped files before handing the input to the engine, so the
    engine itself stays pure-text and easily testable.
    """

    name: str
    text: str


@dataclass(frozen=True)
class SBIRInput:
    topic_number: str
    topic_title: str | None
    component: str
    topic_source_kind: Literal["pdf", "url", "text"]
    topic_payload: str
    topic_close_date: str | None
    synergy_hypothesis: str
    attachments: list[SBIRAttachment] = field(default_factory=list)
    resource_links: list[str] = field(default_factory=list)
    sister_proposals: list[str] = field(default_factory=list)
    special_instructions: str | None = None
    depth: Depth = "standard"


@dataclass(frozen=True)
class SBIREvent:
    kind: Literal[
        "phase_start",
        "delta",
        "file_written",
        "phase_complete",
        "error",
        "final",
    ]
    phase: str | None = None
    label: str | None = None
    text: str | None = None
    path: str | None = None
    bytes_: int | None = None
    duration_ms: int | None = None
    message: str | None = None
    # Final-only:
    output_dir: str | None = None
    file_count: int | None = None
    verify_flags: tuple[str, ...] | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class _PhaseRun:
    """Mutable state accumulated during one phase's streaming call."""

    text: str = ""
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def _format_input_summary(inp: SBIRInput) -> str:
    """Compact, machine-readable summary the model can quote back."""
    sister = (
        "\n".join(f"  - {s}" for s in inp.sister_proposals)
        if inp.sister_proposals
        else "  (none disclosed)"
    )
    links = "\n".join(f"  - {u}" for u in inp.resource_links) if inp.resource_links else "  (none)"
    attachments = (
        "\n".join(f"  - {a.name} ({len(a.text)} chars)" for a in inp.attachments)
        if inp.attachments
        else "  (none)"
    )
    special = inp.special_instructions or "(none)"
    return (
        f"Topic number: {inp.topic_number}\n"
        f"Topic title: {inp.topic_title or '(not provided)'}\n"
        f"Component: {inp.component}\n"
        f"Topic source kind: {inp.topic_source_kind}\n"
        f"Topic close date: {inp.topic_close_date or '(not provided)'}\n"
        f"Depth: {inp.depth}\n"
        f"Synergy hypothesis: {inp.synergy_hypothesis.strip()}\n"
        f"Sister proposals:\n{sister}\n"
        f"Resource links:\n{links}\n"
        f"Attachments:\n{attachments}\n"
        f"Special instructions: {special}\n"
    )


def _format_attachments_block(attachments: list[SBIRAttachment]) -> str:
    if not attachments:
        return "(no attachments)"
    parts: list[str] = []
    for a in attachments:
        # Cap each attachment to keep prompts bounded.
        body = a.text.strip()
        if len(body) > 12_000:
            body = body[:12_000] + "\n…[truncated]"
        parts.append(f"### {a.name}\n\n{body}\n")
    return "\n".join(parts)


async def _run_phase(
    client: AnthropicLLMClient,
    system_prompt: str,
    user_message: str,
    *,
    purpose: str,
    max_tokens: int,
) -> AsyncIterator[tuple[str, _PhaseRun]]:
    """Stream one phase. Yields (delta_text, run_state_so_far) tuples.

    The final yield carries the empty string as delta and the fully-
    populated `_PhaseRun` (model + tokens). Callers persist + react.
    """
    run = _PhaseRun()
    async for chunk in client.complete_stream(
        system=system_prompt,
        user=user_message,
        complexity="smart",
        max_tokens=max_tokens,
        purpose=purpose,
    ):
        if chunk.kind == "delta":
            run.text += chunk.text
            yield chunk.text, run
        elif chunk.kind == "final":
            run.model = chunk.model
            run.input_tokens = chunk.input_tokens or 0
            run.output_tokens = chunk.output_tokens or 0
            yield "", run


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


async def run_sbir_submission(
    client: AnthropicLLMClient,
    inp: SBIRInput,
    *,
    write_artifact,  # callable: (relpath: str, content: str) -> int (bytes written)
    output_dir_for_final: str,
) -> AsyncIterator[SBIREvent]:
    """Drive the engine end-to-end. See module docstring for event shapes."""

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    input_summary = _format_input_summary(inp)
    attachments_block = _format_attachments_block(inp.attachments)

    total_input_tokens = 0
    total_output_tokens = 0
    last_model: str | None = None
    verify_flags: set[str] = set()
    files_written: list[str] = []

    def _harvest_flags(text: str) -> None:
        for match in _VERIFY_RE.findall(text):
            verify_flags.add(match.strip())

    async def _stream_phase_to_file(
        phase_key: str,
        label: str,
        user_message: str,
        relpath: str,
        max_tokens: int,
    ) -> str:
        """Stream one phase, write its text to disk, emit events.

        Returns the full text produced. Caller uses it as context for
        subsequent phases.
        """
        nonlocal total_input_tokens, total_output_tokens, last_model
        yield SBIREvent(kind="phase_start", phase=phase_key, label=label)
        started = _now_ms()
        text_so_far = ""
        async for delta, run in _run_phase(
            client,
            system_prompt,
            user_message,
            purpose=f"sbir:{PROMPT_VERSION}:{phase_key}",
            max_tokens=max_tokens,
        ):
            if delta:
                text_so_far = run.text
                yield SBIREvent(kind="delta", phase=phase_key, text=delta)
            elif run.model:
                last_model = run.model
                total_input_tokens += run.input_tokens
                total_output_tokens += run.output_tokens
        body = text_so_far.strip()
        _harvest_flags(body)
        bytes_written = write_artifact(relpath, body + "\n")
        files_written.append(relpath)
        yield SBIREvent(
            kind="file_written",
            phase=phase_key,
            path=relpath,
            bytes_=bytes_written,
        )
        yield SBIREvent(
            kind="phase_complete",
            phase=phase_key,
            duration_ms=_now_ms() - started,
        )
        # Stash for caller via the closure (handled below — see locals).
        _state["last_body"] = body

    # Tiny shim so the generator above can communicate text out to the
    # outer driver without re-streaming. async generators can't return a
    # value via `return` inside `yield`, and we can't yield the body too
    # without breaking the SSE consumer's typing — so we stash it on a
    # mutable dict the outer caller reads after the inner generator ends.
    _state: dict[str, str] = {"last_body": ""}

    async def _drive(
        phase_key: str, label: str, user_message: str, relpath: str, max_tokens: int
    ) -> str:
        async for evt in _stream_phase_to_file(phase_key, label, user_message, relpath, max_tokens):
            yield evt
        # `_state["last_body"]` is now populated.

    # ---- Phase 0: intake validation ----
    yield SBIREvent(kind="phase_start", phase="intake", label="Phase 0 — Intake validation")
    started = _now_ms()
    intake_user = build_intake_user_message(input_summary)
    intake_text = ""
    async for delta, run in _run_phase(
        client,
        system_prompt,
        intake_user,
        purpose=f"sbir:{PROMPT_VERSION}:intake",
        max_tokens=200,
    ):
        if delta:
            intake_text = run.text
            yield SBIREvent(kind="delta", phase="intake", text=delta)
        elif run.model:
            last_model = run.model
            total_input_tokens += run.input_tokens
            total_output_tokens += run.output_tokens
    yield SBIREvent(
        kind="phase_complete",
        phase="intake",
        duration_ms=_now_ms() - started,
    )
    intake_first = intake_text.strip().splitlines()[0] if intake_text.strip() else ""
    if not intake_first.startswith("VALIDATION_OK"):
        msg = intake_first or "intake validation produced no verdict"
        yield SBIREvent(kind="error", message=f"Phase 0 halt: {msg}"[:400])
        yield SBIREvent(
            kind="final",
            output_dir=output_dir_for_final,
            file_count=len(files_written),
            verify_flags=tuple(sorted(verify_flags)),
            model=last_model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
        return

    # ---- Phase 1: topic analysis ----
    topic_payload_block = f"{inp.topic_payload}\n\n--- USER ATTACHMENTS ---\n{attachments_block}"
    topic_extract = ""
    async for evt in _drive(
        "topic_analysis",
        "Phase 1 — Topic analysis",
        build_topic_extract_user_message(input_summary, topic_payload_block),
        "topic-extract.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt
    topic_extract = _state["last_body"]

    if inp.depth == "scaffold":
        # Skip Phases 2-4 and 6-7. Produce only Vol 1 + DSIP cheat sheet.
        for spec in VOLUME_SPECS:
            if spec.key not in SCAFFOLD_VOLUME_KEYS:
                continue
            context = f"--- INPUTS ---\n{input_summary}\n\n--- TOPIC EXTRACT ---\n{topic_extract}\n"
            async for evt in _drive(
                f"phase5:{spec.key}",
                f"Phase 5 — {spec.label}",
                build_volume_user_message(spec, context),
                spec.relpath,
                DEFAULT_MAX_TOKENS_LONG if spec.key == "volume_1" else DEFAULT_MAX_TOKENS_SHORT,
            ):
                yield evt
        yield SBIREvent(
            kind="final",
            output_dir=output_dir_for_final,
            file_count=len(files_written),
            verify_flags=tuple(sorted(verify_flags)),
            model=last_model,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )
        return

    # ---- Phase 2: synergy ----
    async for evt in _drive(
        "synergy",
        "Phase 2 — Firm-fit + synergy validation",
        build_synergy_user_message(input_summary, topic_extract, inp.synergy_hypothesis),
        "synergy-assessment.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt
    synergy_assessment = _state["last_body"]

    # ---- Phase 3: strategy ----
    async for evt in _drive(
        "strategy",
        "Phase 3 — Strategy and structure",
        build_strategy_user_message(input_summary, topic_extract, synergy_assessment),
        "strategy.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt
    strategy = _state["last_body"]

    # ---- Phase 4: overclaim audit ----
    async for evt in _drive(
        "overclaim",
        "Phase 4 — Overclaim audit",
        build_overclaim_user_message(input_summary, topic_extract, synergy_assessment, strategy),
        "overclaim-audit.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt
    overclaim = _state["last_body"]

    # ---- Phase 5: volumes ----
    generated_bodies: dict[str, str] = {
        "topic-extract.md": topic_extract,
        "synergy-assessment.md": synergy_assessment,
        "strategy.md": strategy,
        "overclaim-audit.md": overclaim,
    }
    for spec in VOLUME_SPECS:
        context = _build_volume_context(input_summary, generated_bodies, inp.attachments, spec)
        max_tokens = (
            DEFAULT_MAX_TOKENS_LONG
            if spec.key in {"volume_2", "volume_3"}
            else DEFAULT_MAX_TOKENS_SHORT
        )
        async for evt in _drive(
            f"phase5:{spec.key}",
            f"Phase 5 — {spec.label}",
            build_volume_user_message(spec, context),
            spec.relpath,
            max_tokens,
        ):
            yield evt
        generated_bodies[spec.relpath] = _state["last_body"]

    # ---- Phase 6: consistency sweep ----
    consistency_payload = _format_generated_files(generated_bodies)
    async for evt in _drive(
        "consistency",
        "Phase 6 — Cross-artifact consistency sweep",
        build_consistency_user_message(consistency_payload),
        "inconsistency-report.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt

    # ---- Phase 7: preflight ----
    async for evt in _drive(
        "preflight",
        "Phase 7 — Pre-flight checklist",
        build_preflight_user_message(input_summary, sorted(verify_flags)),
        "preflight.md",
        DEFAULT_MAX_TOKENS_SHORT,
    ):
        yield evt

    if inp.depth == "complete":
        # PDF/Excel/DOCX rendering pipeline not yet wired up. Surface a
        # flag so the UI shows the user why no renders appeared, but
        # don't fail — the markdown bundle is complete and usable.
        verify_flags.add(
            "⚠️ VERIFY: Complete-depth rendering (PDF/Excel/DOCX) is not yet "
            "implemented in this build. Markdown package is complete; render "
            "manually for now."
        )

    yield SBIREvent(
        kind="final",
        output_dir=output_dir_for_final,
        file_count=len(files_written),
        verify_flags=tuple(sorted(verify_flags)),
        model=last_model,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
    )


def _build_volume_context(
    input_summary: str,
    generated_bodies: dict[str, str],
    attachments: list[SBIRAttachment],
    spec: VolumeSpec,
) -> str:
    """Pack the prior-phase outputs into the user message for one volume.

    Volume 5 supporting docs (CVs, bibliography, partner LOS index) often
    just need topic extract + strategy. Vol 2 needs everything. The cheap
    play is "send everything we have"; prompts are cached and the model
    can ignore what it doesn't need.
    """
    parts = [f"--- INPUTS ---\n{input_summary}"]
    for label, body in generated_bodies.items():
        parts.append(f"--- {label.upper()} ---\n{body.strip()}")
    if attachments:
        parts.append("--- USER ATTACHMENTS ---\n" + _format_attachments_block(attachments))
    parts.append(f"--- THIS PHASE TARGET FILE ---\n{spec.relpath}")
    return "\n\n".join(parts)


def _format_generated_files(bodies: dict[str, str]) -> str:
    parts: list[str] = []
    for relpath, body in bodies.items():
        parts.append(f"### {relpath}\n\n{body.strip()}\n")
    return "\n".join(parts)


__all__ = [
    "PROMPT_VERSION",
    "Depth",
    "SBIRAttachment",
    "SBIREvent",
    "SBIRInput",
    "run_sbir_submission",
]


# Reserved for future per-phase telemetry payloads.
_ = json
