"""Tenant eligibility — aggregated bid-readiness signal.

Single endpoint that rolls up everything CaptureOS knows about whether
the tenant can legally and operationally bid right now:

* B1/B2: SAM.gov registration status + expiration (synced daily by
  ``mactech.tenant.verify_sam``).
* B3-on-self: federal exclusions / debarment check on the tenant's
  own UEI.
* B5: set-aside certifications held (synced from SAM Entity at
  onboarding).
* B6: cyber posture (SPRS score + assessment date; deeper per-opp
  analysis lives in ``cyber-summary``).
* B7: governance readiness (FCL, accounting system, E-Verify, reps &
  certs) — currently stub until GovernanceOS lands.

The ``blockers`` array is the punch list a capture lead needs before
green-lighting a bid: human-readable, actionable, prioritized.
"""

from __future__ import annotations

import logging
from datetime import date as date_t
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from mactech_api.auth import RequestContext, get_request_context

log = logging.getLogger(__name__)
router = APIRouter(tags=["eligibility"])

# Days before expiration we start surfacing a warning blocker.
EXPIRATION_WARNING_DAYS = 30


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SamRegistrationOut(_Out):
    status: str  # active | expired | invalid | unverified
    registration_date: str | None
    expires_at: str | None
    days_until_expiration: int | None
    last_checked_at: str | None


class ExclusionsOut(_Out):
    is_excluded: bool
    record_count: int
    last_checked_at: str | None


class CyberPostureBlock(_Out):
    sprs_score: int | None
    sprs_max: int
    sprs_assessment_date: str | None
    sprs_synced_at: str | None


class GovernanceReadinessBlock(_Out):
    """Stub block until GovernanceOS lands. Today these all return null —
    the field shape is published so consumers can deserialize a stable
    schema and the UI can show a "GovernanceOS not yet wired" callout."""

    accounting_system_dcaa_ready: bool | None = None
    fcl_status: str | None = None
    fcl_level: str | None = None
    e_verify_enrolled: bool | None = None
    reps_certs_current: bool | None = None
    source: str = "stub"


class TenantEligibilityOut(_Out):
    tenant_slug: str
    uei: str | None
    cage_code: str | None
    set_aside_certifications: list[str]
    sam_registration: SamRegistrationOut
    exclusions: ExclusionsOut
    cyber: CyberPostureBlock
    governance: GovernanceReadinessBlock
    blockers: list[str]
    has_hard_blocker: bool


def _days_until(d: date_t | None) -> int | None:
    if d is None:
        return None
    return (d - date_t.today()).days


def _build_blockers(
    *,
    uei: str | None,
    sam_status: str,
    expires_at: date_t | None,
    is_excluded: bool,
    record_count: int,
    sprs_score: int | None,
    set_asides: list[str],
) -> tuple[list[str], bool]:
    """Return (blockers, has_hard_blocker).

    Hard blockers stop bidding entirely (debarment, expired
    registration, no UEI). Soft blockers are warnings that need
    attention but don't kill the bid.
    """
    blockers: list[str] = []
    hard = False

    if not uei:
        blockers.append(
            "No UEI on file. Add the company's UEI in Settings before "
            "bidding any federal opportunity."
        )
        hard = True

    if is_excluded:
        blockers.append(
            f"Company appears on the federal exclusions list "
            f"({record_count} record(s)). Federal contracting is barred "
            "until the exclusion is lifted."
        )
        hard = True

    if sam_status == "expired":
        blockers.append(
            "SAM.gov registration is EXPIRED. Renew at SAM.gov before "
            "submitting any proposal — non-current registration is "
            "disqualifying under FAR 52.204-7."
        )
        hard = True
    elif sam_status == "invalid":
        blockers.append(
            "SAM.gov could not verify the registration. The UEI may be "
            "wrong or the entity may not be active. Confirm at SAM.gov."
        )
        hard = True
    elif sam_status == "unverified":
        blockers.append(
            "SAM.gov registration has not been verified yet. The daily "
            "verification worker runs at 06:30 ET; check back tomorrow."
        )

    days_left = _days_until(expires_at)
    if sam_status == "active" and days_left is not None and days_left <= EXPIRATION_WARNING_DAYS:
        blockers.append(
            f"SAM.gov registration expires in {days_left} day(s) "
            f"({expires_at.isoformat() if expires_at else '?'}). Renew now "
            "to avoid a gap that would invalidate any in-flight bids."
        )
        # Soft blocker — bidding is still permitted today.

    if not set_asides:
        blockers.append(
            "No set-aside certifications captured. Set-aside opportunities "
            "(SDVOSB, 8(a), HUBZone, WOSB) require a current cert. Confirm "
            "in Settings."
        )

    if sprs_score is None:
        blockers.append(
            "No SPRS score on file. DFARS 252.204-7019 / 7020 opportunities "
            "require a current self-assessment in SPRS. Sync from Codex."
        )

    return blockers, hard


@router.get(
    "/tenant/eligibility",
    response_model=TenantEligibilityOut,
)
async def get_tenant_eligibility(
    ctx: Annotated[RequestContext, Depends(get_request_context)],
) -> TenantEligibilityOut:
    t = ctx.tenant

    sam_status: str = t.sam_registration_status or "unverified"
    sam_block = SamRegistrationOut(
        status=sam_status,
        registration_date=(
            t.sam_registration_date.isoformat() if t.sam_registration_date else None
        ),
        expires_at=(
            t.sam_registration_expires_at.isoformat() if t.sam_registration_expires_at else None
        ),
        days_until_expiration=_days_until(t.sam_registration_expires_at),
        last_checked_at=(
            t.sam_registration_last_checked_at.isoformat()
            if t.sam_registration_last_checked_at
            else None
        ),
    )
    exclusions_block = ExclusionsOut(
        is_excluded=t.is_excluded,
        record_count=t.exclusions_record_count,
        last_checked_at=(
            t.exclusions_last_checked_at.isoformat() if t.exclusions_last_checked_at else None
        ),
    )
    cyber_block = CyberPostureBlock(
        sprs_score=t.sprs_score,
        sprs_max=t.sprs_max or 110,
        sprs_assessment_date=(
            t.sprs_assessment_date.isoformat() if t.sprs_assessment_date else None
        ),
        sprs_synced_at=(t.sprs_synced_at.isoformat() if t.sprs_synced_at else None),
    )

    set_asides = list(t.set_aside_certifications or [])
    blockers, hard = _build_blockers(
        uei=t.uei,
        sam_status=sam_status,
        expires_at=t.sam_registration_expires_at,
        is_excluded=t.is_excluded,
        record_count=t.exclusions_record_count,
        sprs_score=t.sprs_score,
        set_asides=set_asides,
    )

    return TenantEligibilityOut(
        tenant_slug=t.slug,
        uei=t.uei,
        cage_code=t.cage_code,
        set_aside_certifications=set_asides,
        sam_registration=sam_block,
        exclusions=exclusions_block,
        cyber=cyber_block,
        governance=GovernanceReadinessBlock(),
        blockers=blockers,
        has_hard_blocker=hard,
    )
