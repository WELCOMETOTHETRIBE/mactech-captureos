from datetime import date, datetime
from uuid import UUID

from sqlalchemy import TIMESTAMP, Boolean, Date, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    plan: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'scout'"))
    uei: Mapped[str | None] = mapped_column(String, nullable=True)
    cage_code: Mapped[str | None] = mapped_column(String, nullable=True)
    clerk_org_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # Set-aside certifications the tenant claims (SDVOSB, 8(a), HUBZone,
    # WOSB, EDWOSB, VOSB, SDB, SB). Drives the proposal drafter's set-aside
    # qualification section + the opportunity scoring engine's set-aside fit
    # signal. Auto-populated from SAM Entity API on UEI lookup; user editable.
    set_aside_certifications: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    # NAICS codes the tenant wants opportunities scored against. Set by the
    # onboarding wizard (NAICS picker, defaulted from SAM Entity API result).
    # When null, the scoring engine falls back to the seed-config NAICS list.
    # When set, it overrides the seed config for that tenant.
    target_naics: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    # When the tenant finished onboarding. NULL means the wizard hasn't run
    # yet (or was reset); the dashboard surfaces a "Finish setup" banner
    # while this is null. We don't gate routes on it — onboarding is a
    # discoverable affordance, not a forced wall.
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Supplier Performance Risk System score — DoD-published per-org
    # NIST 800-171 self-assessment number that gates DFARS 7012 / CMMC
    # eligibility. CaptureOS doesn't manage the assessment workflow
    # (that lives in Codex, codex.mactechsolutionsllc.com); we just
    # consume the published number for display + scoring eligibility.
    sprs_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sprs_max: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("110")
    )
    sprs_assessment_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    sprs_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sprs_synced_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # SAM.gov registration verification (B1, B2). The
    # mactech.tenant.verify_sam worker keeps these fresh daily by
    # hitting SAM Entity API. ``sam_registration_status`` is "active",
    # "expired", "invalid", or null until first check.
    sam_registration_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    sam_registration_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    sam_registration_expires_at: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )
    sam_registration_last_checked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # Federal exclusions / debarment check on the tenant's own UEI (B3).
    is_excluded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    exclusions_record_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    exclusions_last_checked_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
