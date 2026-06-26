"""SBIR Submission Engine — multi-phase agent + file artifacts.

Surfaces the engine spec at docs/prompts/sbir-submission-engine.md as a
real product feature in the captureOS web app.

Endpoints:

  POST /sbir/generate/stream                  SSE: phase-by-phase run
  POST /sbir/decode/file                      multipart upload → decoded text
  GET  /sbir/submissions                      list (newest first)
  GET  /sbir/submissions/{id}                 single
  GET  /sbir/submissions/{id}/files/{path}    download one artifact file
  GET  /sbir/topics                           topic feed (filter + paginate)
  GET  /sbir/topics/{id}                      one topic
  POST /sbir/topics/refresh                   kick the Apify ingest worker

The streaming endpoint accepts JSON — attachments are pre-decoded by the
client via /sbir/decode/file and POSTed as `{name, text}` pairs in the
generate request body. Keeping decode out-of-band means the streaming
endpoint stays pure-JSON (browsers can't multipart-POST an SSE response).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from mactech_db.models import SBIR_DEPTHS, SBIRSubmission, SBIRTopic
from mactech_intelligence import (
    AnthropicLLMClient,
    SBIRAttachment,
    SBIRInput,
    run_sbir_submission,
)
from mactech_intelligence.sbir_submission_engine import PROMPT_VERSION
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select

from mactech_api.auth import RequestContext, get_request_context
from mactech_api.sbir_workspace import SBIRWorkspace

log = logging.getLogger(__name__)
router = APIRouter(tags=["sbir"])

_VALID_DEPTHS = set(SBIR_DEPTHS)
_VALID_COMPONENTS = {
    "Army",
    "Navy",
    "Air Force",
    "DLA",
    "DARPA",
    "SOCOM",
    "Other",
}


# ---------- pydantic schemas ----------


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SBIRSubmissionAttachment(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=200_000)


class SBIRGenerateRequest(BaseModel):
    topic_number: str = Field(min_length=3, max_length=64)
    topic_title: str | None = Field(default=None, max_length=512)
    component: str = Field(min_length=1, max_length=32)
    topic_source_kind: str = Field(pattern=r"^(pdf|url|text)$")
    topic_payload: str = Field(min_length=10, max_length=500_000)
    topic_close_date: str | None = Field(default=None, max_length=64)
    synergy_hypothesis: str = Field(min_length=10, max_length=8_000)
    attachments: list[SBIRSubmissionAttachment] = Field(default_factory=list, max_length=20)
    resource_links: list[str] = Field(default_factory=list, max_length=20)
    sister_proposals: list[str] = Field(default_factory=list, max_length=20)
    special_instructions: str | None = Field(default=None, max_length=4_000)
    depth: str = Field(pattern=r"^(scaffold|standard|complete)$")


class SBIRSubmissionFile(BaseModel):
    path: str
    bytes: int


class SBIRSubmissionOut(_Out):
    id: str
    topic_number: str
    topic_title: str | None
    proposal_title: str | None
    component: str
    depth: str
    status: str
    output_dir: str
    verify_flags: list[str]
    file_count: int
    error: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    files: list[SBIRSubmissionFile] = Field(default_factory=list)


class SBIRSubmissionListItem(_Out):
    id: str
    topic_number: str
    topic_title: str | None
    component: str
    depth: str
    status: str
    file_count: int
    created_at: str
    completed_at: str | None


class SBIRSubmissionListResponse(_Out):
    total: int
    items: list[SBIRSubmissionListItem]


class SBIRDecodedFile(_Out):
    name: str
    kind: str  # "pdf" | "text"
    text: str
    char_count: int
    truncated: bool


# ---------- file decode (PDF + text-shaped attachments) ----------


_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_DECODED_CHARS = 200_000  # matches generate request attachment limit
_TEXT_EXTS = {".txt", ".md", ".markdown", ".json", ".yaml", ".yml", ".csv", ".tsv"}


@router.post("/sbir/decode/file", response_model=SBIRDecodedFile)
async def decode_sbir_file(
    _ctx: Annotated[RequestContext, Depends(get_request_context)],
    file: UploadFile = File(...),  # noqa: B008 — FastAPI's required idiom
) -> SBIRDecodedFile:
    """Decode an uploaded PDF or text file to plain text.

    The web form uses this for the topic-source PDF tab and the
    attachments multi-file picker so the generate endpoint can stay
    pure-JSON. Rejects images and unknown binary formats — the engine
    only consumes text.
    """
    blob = await file.read()
    if len(blob) == 0:
        raise HTTPException(status_code=400, detail="empty file")
    if len(blob) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )

    name = (file.filename or "upload").strip() or "upload"
    lower = name.lower()
    text = ""
    kind = "text"

    if lower.endswith(".pdf"):
        try:
            import fitz  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover — pymupdf is in deps
            raise HTTPException(
                status_code=500, detail="PDF decoding unavailable on this host"
            ) from exc
        try:
            with fitz.open(stream=blob, filetype="pdf") as doc:
                text = "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"could not parse PDF: {exc}"[:200]
            ) from exc
        kind = "pdf"
    elif any(lower.endswith(ext) for ext in _TEXT_EXTS) or lower.endswith(
        (".log", ".html", ".htm", ".xml")
    ):
        text = blob.decode("utf-8", errors="replace")
    else:
        # No extension or unrecognized — try utf-8 decode but fail if the
        # result is mostly binary noise (>5% replacement chars = reject).
        candidate = blob.decode("utf-8", errors="replace")
        noise_ratio = candidate.count("�") / max(len(candidate), 1)
        if noise_ratio > 0.05:
            raise HTTPException(
                status_code=415,
                detail=(
                    "unsupported file type — engine accepts PDF or text "
                    "(txt / md / json / yaml / csv). Images and binaries "
                    "are not supported."
                ),
            )
        text = candidate

    text = text.strip()
    if len(text) < 10:
        raise HTTPException(
            status_code=400, detail="could not extract enough text (less than 10 chars)"
        )

    truncated = False
    if len(text) > _MAX_DECODED_CHARS:
        text = text[:_MAX_DECODED_CHARS]
        truncated = True

    return SBIRDecodedFile(
        name=name,
        kind=kind,
        text=text,
        char_count=len(text),
        truncated=truncated,
    )


# ---------- helpers ----------


def _serialize_submission(
    sub: SBIRSubmission, files: list[SBIRSubmissionFile]
) -> SBIRSubmissionOut:
    return SBIRSubmissionOut(
        id=str(sub.id),
        topic_number=sub.topic_number,
        topic_title=sub.topic_title,
        proposal_title=sub.proposal_title,
        component=sub.component,
        depth=sub.depth,
        status=sub.status,
        output_dir=sub.output_dir,
        verify_flags=list(sub.verify_flags or []),
        file_count=sub.file_count,
        error=sub.error,
        model=sub.model,
        input_tokens=sub.input_tokens,
        output_tokens=sub.output_tokens,
        created_at=sub.created_at.isoformat(),
        started_at=sub.started_at.isoformat() if sub.started_at else None,
        completed_at=sub.completed_at.isoformat() if sub.completed_at else None,
        files=files,
    )


def _list_workspace_files(workspace: SBIRWorkspace) -> list[SBIRSubmissionFile]:
    return [SBIRSubmissionFile(path=p, bytes=b) for p, b in workspace.list_files()]


# ---------- endpoints ----------


@router.post(
    "/sbir/generate/stream",
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "SSE stream of {type:'phase_start'|'delta'|'file_written'|"
                "'phase_complete'|'error'|'final',...}"
            ),
        }
    },
)
async def generate_sbir_submission_stream(
    body: SBIRGenerateRequest,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> StreamingResponse:
    """Run the full multi-phase SBIR Submission Engine.

    Validates inputs, registers a `sbir_submissions` row (status=running),
    streams phase events back as SSE, writes artifacts to disk under
    `docs/sbir-{topic}/submission/`, and on completion updates the row
    with verify flags + token totals.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )
    if body.depth not in _VALID_DEPTHS:
        raise HTTPException(status_code=422, detail=f"invalid depth: {body.depth}")
    if body.component not in _VALID_COMPONENTS:
        raise HTTPException(
            status_code=422,
            detail=f"invalid component: {body.component} (allowed: {sorted(_VALID_COMPONENTS)})",
        )

    # Duplicate-topic check (engine Phase 0). The DB constraint is the
    # backstop; we surface a friendlier 409 here before starting the run.
    existing = (
        await ctx.session.execute(
            select(SBIRSubmission).where(
                SBIRSubmission.tenant_id == ctx.tenant.id,
                SBIRSubmission.topic_number == body.topic_number,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"submission already exists for topic {body.topic_number} "
                f"(id={existing.id}, status={existing.status}). "
                "Delete or rename before re-submitting."
            ),
        )

    try:
        workspace = SBIRWorkspace.for_topic(body.topic_number)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    workspace.ensure()

    submission = SBIRSubmission(
        tenant_id=ctx.tenant.id,
        created_by_founder_id=ctx.founder.id if ctx.founder else None,
        topic_number=body.topic_number,
        topic_title=body.topic_title,
        component=body.component,
        depth=body.depth,
        status="running",
        output_dir=workspace.relative_to_repo,
        verify_flags=[],
        file_count=0,
        prompt_version=PROMPT_VERSION,
        started_at=datetime.now(UTC),
    )
    ctx.session.add(submission)
    await ctx.session.flush()
    submission_id = submission.id
    tenant_id = ctx.tenant.id
    # Capture by value — ctx.session is closed when this handler returns
    # the StreamingResponse.

    engine_input = SBIRInput(
        topic_number=body.topic_number,
        topic_title=body.topic_title,
        component=body.component,
        topic_source_kind=body.topic_source_kind,  # type: ignore[arg-type]
        topic_payload=body.topic_payload,
        topic_close_date=body.topic_close_date,
        synergy_hypothesis=body.synergy_hypothesis,
        attachments=[SBIRAttachment(name=a.name, text=a.text) for a in body.attachments],
        resource_links=list(body.resource_links),
        sister_proposals=list(body.sister_proposals),
        special_instructions=body.special_instructions,
        depth=body.depth,  # type: ignore[arg-type]
    )

    async def event_stream() -> AsyncIterator[bytes]:
        client = AnthropicLLMClient(api_key=api_key)

        def _write(relpath: str, content: str) -> int:
            target = workspace.write_artifact(relpath, content)
            return target.stat().st_size

        final_verify: list[str] = []
        final_model: str | None = None
        final_in_tokens: int | None = None
        final_out_tokens: int | None = None
        final_file_count = 0
        had_halt = False

        try:
            async for evt in run_sbir_submission(
                client,
                engine_input,
                write_artifact=_write,
                output_dir_for_final=workspace.relative_to_repo,
            ):
                payload: dict[str, object] = {"type": evt.kind}
                if evt.phase is not None:
                    payload["phase"] = evt.phase
                if evt.label is not None:
                    payload["label"] = evt.label
                if evt.text is not None:
                    payload["text"] = evt.text
                if evt.path is not None:
                    payload["path"] = evt.path
                if evt.bytes_ is not None:
                    payload["bytes"] = evt.bytes_
                if evt.duration_ms is not None:
                    payload["duration_ms"] = evt.duration_ms
                if evt.message is not None:
                    payload["message"] = evt.message
                    had_halt = True
                if evt.kind == "final":
                    final_verify = list(evt.verify_flags or ())
                    final_model = evt.model
                    final_in_tokens = evt.input_tokens
                    final_out_tokens = evt.output_tokens
                    final_file_count = evt.file_count or 0
                    payload.update(
                        {
                            "submission_id": str(submission_id),
                            "output_dir": evt.output_dir,
                            "file_count": final_file_count,
                            "verify_flags": final_verify,
                            "model": final_model,
                            "input_tokens": final_in_tokens,
                            "output_tokens": final_out_tokens,
                        }
                    )
                yield f"data: {json.dumps(payload)}\n\n".encode()
        except Exception as exc:
            log.exception("sbir generation failed: %s", exc)
            err = {
                "type": "error",
                "message": f"{exc.__class__.__name__}: {exc}"[:300],
            }
            yield f"data: {json.dumps(err)}\n\n".encode()
            await _finalize_submission(
                submission_id,
                tenant_id,
                status_value="failed",
                error=f"{exc.__class__.__name__}: {exc}"[:1000],
            )
            return

        await _finalize_submission(
            submission_id,
            tenant_id,
            status_value="failed" if had_halt else "completed",
            verify_flags=final_verify,
            file_count=final_file_count,
            model=final_model,
            input_tokens=final_in_tokens,
            output_tokens=final_out_tokens,
            error=None,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


async def _finalize_submission(
    submission_id: UUID,
    tenant_id: UUID,
    *,
    status_value: str,
    verify_flags: list[str] | None = None,
    file_count: int | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> None:
    from mactech_db import scoped_session

    try:
        async with scoped_session(tenant_id) as session:
            sub = (
                await session.execute(
                    select(SBIRSubmission).where(SBIRSubmission.id == submission_id)
                )
            ).scalar_one_or_none()
            if sub is None:
                log.warning("submission %s vanished during finalize", submission_id)
                return
            sub.status = status_value
            if verify_flags is not None:
                sub.verify_flags = verify_flags
            if file_count is not None:
                sub.file_count = file_count
            if model is not None:
                sub.model = model
            if input_tokens is not None:
                sub.input_tokens = input_tokens
            if output_tokens is not None:
                sub.output_tokens = output_tokens
            if error is not None:
                sub.error = error
            sub.completed_at = datetime.now(UTC)
    except Exception as exc:
        log.exception("failed to finalize submission %s: %s", submission_id, exc)


@router.get(
    "/sbir/submissions",
    response_model=SBIRSubmissionListResponse,
)
async def list_sbir_submissions(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SBIRSubmissionListResponse:
    rows = (
        (
            await ctx.session.execute(
                select(SBIRSubmission)
                .where(SBIRSubmission.tenant_id == ctx.tenant.id)
                .order_by(desc(SBIRSubmission.created_at))
            )
        )
        .scalars()
        .all()
    )
    items = [
        SBIRSubmissionListItem(
            id=str(r.id),
            topic_number=r.topic_number,
            topic_title=r.topic_title,
            component=r.component,
            depth=r.depth,
            status=r.status,
            file_count=r.file_count,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in rows
    ]
    return SBIRSubmissionListResponse(total=len(items), items=items)


@router.get(
    "/sbir/submissions/{submission_id}",
    response_model=SBIRSubmissionOut,
)
async def get_sbir_submission(
    submission_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SBIRSubmissionOut:
    sub = (
        await ctx.session.execute(
            select(SBIRSubmission).where(
                SBIRSubmission.id == submission_id,
                SBIRSubmission.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="submission not found")
    try:
        workspace = SBIRWorkspace.for_topic(sub.topic_number)
    except ValueError:
        files: list[SBIRSubmissionFile] = []
    else:
        files = _list_workspace_files(workspace)
    return _serialize_submission(sub, files)


@router.get("/sbir/submissions/{submission_id}/files/{path:path}")
async def download_sbir_artifact(
    submission_id: UUID,
    path: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> FileResponse:
    sub = (
        await ctx.session.execute(
            select(SBIRSubmission).where(
                SBIRSubmission.id == submission_id,
                SBIRSubmission.tenant_id == ctx.tenant.id,
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="submission not found")
    try:
        workspace = SBIRWorkspace.for_topic(sub.topic_number)
        target = workspace.resolve(path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    # Markdown / text content is the common case — let FileResponse pick the
    # MIME by extension. Use the basename as the suggested download name.
    return FileResponse(
        path=target,
        filename=target.name,
        headers={"Cache-Control": "no-store"},
    )


# ---------- topic feed (populated by apify_sbir_topics worker) ----------


class SBIRTopicListItem(_Out):
    id: str
    source: str
    topic_number: str
    title: str | None
    component: str | None
    program: str | None
    phase: str | None
    status: str
    close_date: str | None
    url: str | None


class SBIRTopicListResponse(_Out):
    total: int
    items: list[SBIRTopicListItem]


class SBIRTopicDetail(_Out):
    id: str
    source: str
    topic_number: str
    title: str | None
    component: str | None
    program: str | None
    phase: str | None
    status: str
    prerelease_date: str | None
    open_date: str | None
    close_date: str | None
    description: str | None
    url: str | None
    technology_areas: list[str] | None
    modernization_priorities: list[str] | None
    keywords: list[str] | None
    itar_export_status: str | None
    phase_i_ceiling: int | None
    phase_i_duration_months: int | None
    first_seen_at: str
    last_seen_at: str


def _serialize_topic_list(t: SBIRTopic) -> SBIRTopicListItem:
    return SBIRTopicListItem(
        id=str(t.id),
        source=t.source,
        topic_number=t.topic_number,
        title=t.title,
        component=t.component,
        program=t.program,
        phase=t.phase,
        status=t.status,
        close_date=t.close_date.isoformat() if t.close_date else None,
        url=t.url,
    )


def _serialize_topic_detail(t: SBIRTopic) -> SBIRTopicDetail:
    return SBIRTopicDetail(
        id=str(t.id),
        source=t.source,
        topic_number=t.topic_number,
        title=t.title,
        component=t.component,
        program=t.program,
        phase=t.phase,
        status=t.status,
        prerelease_date=t.prerelease_date.isoformat() if t.prerelease_date else None,
        open_date=t.open_date.isoformat() if t.open_date else None,
        close_date=t.close_date.isoformat() if t.close_date else None,
        description=t.description,
        url=t.url,
        technology_areas=list(t.technology_areas) if t.technology_areas else None,
        modernization_priorities=(
            list(t.modernization_priorities) if t.modernization_priorities else None
        ),
        keywords=list(t.keywords) if t.keywords else None,
        itar_export_status=t.itar_export_status,
        phase_i_ceiling=t.phase_i_ceiling,
        phase_i_duration_months=t.phase_i_duration_months,
        first_seen_at=t.first_seen_at.isoformat(),
        last_seen_at=t.last_seen_at.isoformat(),
    )


@router.get("/sbir/topics", response_model=SBIRTopicListResponse)
async def list_sbir_topics(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
    status: str | None = Query(None, pattern=r"^(prerelease|open|closed|unknown|all)$"),
    component: str | None = Query(None, max_length=64),
    program: str | None = Query(None, pattern=r"^(SBIR|STTR)$"),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=500),
) -> SBIRTopicListResponse:
    """List SBIR topics with optional filtering. Default sort: open
    topics by soonest close date, then everything else by most recently
    seen."""
    _ = ctx  # topics are shared, but we still require auth via the dep
    stmt = select(SBIRTopic)
    if status and status != "all":
        stmt = stmt.where(SBIRTopic.status == status)
    if component:
        stmt = stmt.where(SBIRTopic.component == component)
    if program:
        stmt = stmt.where(SBIRTopic.program == program)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (SBIRTopic.topic_number.ilike(like))
            | (SBIRTopic.title.ilike(like))
            | (SBIRTopic.description.ilike(like))
        )
    # Open topics with a close date first, soonest close on top, then
    # everything else by most-recently-seen.
    stmt = stmt.order_by(
        SBIRTopic.close_date.is_(None).asc(),
        SBIRTopic.close_date.asc(),
        desc(SBIRTopic.last_seen_at),
    ).limit(limit)
    rows = (await ctx.session.execute(stmt)).scalars().all()
    return SBIRTopicListResponse(
        total=len(rows),
        items=[_serialize_topic_list(t) for t in rows],
    )


@router.get("/sbir/topics/{topic_id}", response_model=SBIRTopicDetail)
async def get_sbir_topic(
    topic_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SBIRTopicDetail:
    row = (
        await ctx.session.execute(select(SBIRTopic).where(SBIRTopic.id == topic_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="topic not found")
    return _serialize_topic_detail(row)


class SBIRTopicsRefreshResponse(_Out):
    queued: bool
    task_id: str | None
    detail: str | None


@router.post("/sbir/topics/refresh", response_model=SBIRTopicsRefreshResponse)
async def refresh_sbir_topics(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> SBIRTopicsRefreshResponse:
    """Kick the Apify SBIR topics ingest worker.

    Returns immediately with the Celery task id. The user polls
    /sbir/topics (or the ApifyRun audit table) to see when results
    materialize — the run itself can take 5-10 minutes.
    """
    _ = ctx  # auth required; future: gate to founders only.
    try:
        from mactech_workers.tasks.apify_sbir_topics import (
            kick_sbir_topics_run_task,
        )
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail=f"workers package unavailable: {exc}"
        ) from exc
    try:
        async_result = kick_sbir_topics_run_task.delay()
    except Exception as exc:
        log.warning("could not enqueue sbir-topics kick: %s", exc)
        return SBIRTopicsRefreshResponse(
            queued=False,
            task_id=None,
            detail=f"broker unavailable: {exc.__class__.__name__}",
        )
    return SBIRTopicsRefreshResponse(
        queued=True,
        task_id=str(async_result.id),
        detail=None,
    )
