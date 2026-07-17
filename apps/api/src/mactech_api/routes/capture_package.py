"""Capture Package export endpoint.

Integration contract #1 (CaptureOS → ProposalOS) from
``docs/00_Ecosystem_Overview.md``. See also
``docs/CAPTURE_PACKAGE.md`` for the full handoff narrative.

Endpoint:
  GET /pursuits/{pursuit_id}/capture-package
      Returns the current Capture Package snapshot for a pursuit. Always
      reflects the latest state of the data in CaptureOS — call again to
      get a fresh snapshot.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from mactech_integrations.codex import CodexClient
from mactech_intelligence.capture_package_builder import (
    CapturePackageBuilder,
    OpportunityMissing,
    PursuitNotFound,
)
from mactech_intelligence.schemas import CapturePackage

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["capture-package"])


@router.get(
    "/pursuits/{pursuit_id}/capture-package",
    response_model=CapturePackage,
)
async def get_capture_package(
    pursuit_id: UUID,
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> CapturePackage:
    """Build and return the Capture Package snapshot for a pursuit.

    Always recomputes — no caching. The package reflects the live state
    of CaptureOS at request time.
    """
    base_url = os.environ.get("CODEX_BASE_URL", "https://codex.mactechsolutionsllc.com")
    api_token = os.environ.get("CODEX_API_TOKEN") or None

    async with CodexClient(base_url=base_url, api_token=api_token) as codex:
        builder = CapturePackageBuilder(
            session=ctx.session,
            codex_client=codex,
        )
        try:
            return await builder.build(
                tenant_id=ctx.tenant.id,
                pursuit_id=pursuit_id,
            )
        except PursuitNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"pursuit {pursuit_id} not found",
            ) from exc
        except OpportunityMissing as exc:
            log.error(
                "capture_package: pursuit %s references missing opportunity %s",
                pursuit_id,
                exc.opportunity_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pursuit data is inconsistent — please contact support",
            ) from exc
