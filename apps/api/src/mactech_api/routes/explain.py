"""Plain-English term explainer.

Phase 3 Week 10. Backs the "Explain this" right rail on the
opportunity detail page. Read-through cache:

  GET /explain/{slug}    returns plain-English explanation, hitting
                         Claude Haiku on cache miss and persisting
                         the result to term_explanations.

Slug format: <kind>:<value>
  - "naics:541512"
  - "set_aside:SDVOSB"
  - "notice_type:sources_sought"
  - "score_component:naics_match"

Cache key is (slug, prompt_version) globally — explanations don't
vary by tenant for these kinds. The first tenant to request a term
gets recorded as `first_requested_by_tenant_id` for audit.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from mactech_db.models import TermExplanation
from mactech_intelligence import AnthropicLLMClient, explain_term
from mactech_intelligence.explain_term import PROMPT_VERSION, parse_slug
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["explain"])

# Kept in sync with mactech_intelligence.explain_term._KIND_INTROS. When
# adding a new kind there, mirror it here or the route will 400.
ALLOWED_KINDS = {
    # Original (Phase 3 Week 10)
    "naics",
    "set_aside",
    "notice_type",
    "score_component",
    "agency",
    # Solicitation-decoder + cyber posture jargon (UX inline-helpers sprint)
    "set_aside_cert",
    "clause",
    "cmmc",
    "section",
    "sprs",
    "cui",
    "fci",
    "itar",
    "uei",
    "cage",
    "fcl",
}
MAX_VALUE_LEN = 64


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TermExplanationOut(_Out):
    slug: str
    kind: str
    label: str
    summary: str
    body: str
    cached: bool
    prompt_version: str
    model: str | None


@router.get("/explain/{slug:path}", response_model=TermExplanationOut)
async def get_explanation(
    slug: str,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TermExplanationOut:
    slug = slug.strip()
    if not slug or len(slug) > 128:
        raise HTTPException(status_code=400, detail="invalid slug")
    kind, value = parse_slug(slug)
    if kind not in ALLOWED_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown term kind '{kind}'. Allowed: {sorted(ALLOWED_KINDS)}",
        )
    if not value or len(value) > MAX_VALUE_LEN:
        raise HTTPException(status_code=400, detail="invalid term value")

    # Cache lookup first.
    cached = (
        await ctx.session.execute(
            select(TermExplanation).where(
                TermExplanation.slug == slug,
                TermExplanation.prompt_version == PROMPT_VERSION,
            )
        )
    ).scalar_one_or_none()
    if cached is not None:
        return TermExplanationOut(
            slug=cached.slug,
            kind=cached.kind,
            label=cached.label,
            summary=cached.summary,
            body=cached.body,
            cached=True,
            prompt_version=cached.prompt_version,
            model=cached.model,
        )

    # Cache miss — generate.
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on the API service.",
        )

    client = AnthropicLLMClient(api_key=api_key)
    try:
        result = await explain_term(client, slug)
    except Exception as exc:
        log.exception("explain_term failed for slug=%s: %s", slug, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Anthropic call failed: {exc.__class__.__name__}",
        ) from exc

    row = TermExplanation(
        slug=slug,
        kind=kind,
        label=result.label,
        summary=result.summary,
        body=result.body,
        prompt_version=PROMPT_VERSION,
        model=result.response.model,
        input_tokens=result.response.input_tokens,
        output_tokens=result.response.output_tokens,
        first_requested_by_tenant_id=ctx.tenant.id,
    )
    ctx.session.add(row)
    try:
        await ctx.session.flush()
    except Exception:
        # Race: another request just inserted the same (slug, version).
        # Re-read and return the persisted row.
        await ctx.session.rollback()
        row = (
            await ctx.session.execute(
                select(TermExplanation).where(
                    TermExplanation.slug == slug,
                    TermExplanation.prompt_version == PROMPT_VERSION,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(  # noqa: B904
                status_code=500, detail="explanation persistence race"
            )

    return TermExplanationOut(
        slug=row.slug,
        kind=row.kind,
        label=row.label,
        summary=row.summary,
        body=row.body,
        cached=False,
        prompt_version=row.prompt_version,
        model=row.model,
    )
