"""Capture Package builder — assembles a snapshot of a pursuit for export.

Produces a :class:`CapturePackage` from the current state of a pursuit in
CaptureOS. See ``docs/CAPTURE_PACKAGE.md`` for the contract.

V1 honesty: many sections are sparse today. We populate what we can from
existing tables and report empty/null for what isn't captured yet (full
solicitation file ingest, structured compliance/requirements matrices,
GovernanceOS readiness facts). The :class:`PackageCompleteness` summary
makes those gaps observable rather than hidden.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db.models import (
    ComplianceMatrixItem,
    EvaluationPassFailItem,
    EvaluationScoredFactor,
    Founder,
    OpportunityAmendment,
    OpportunityBrief,
    OpportunityEnriched,
    OpportunityQuestion,
    OpportunityRaw,
    OpportunityScore,
    PastPerformance,
    Pursuit,
    PursuitKeyPersonnel,
    PursuitPastPerformance,
    PursuitTeamingPartner,
    RequirementMatrixItem,
    SolicitationExtraction,
    TeamingPartner,
    Tenant,
    User,
)
from mactech_intelligence.schemas.capture_package import (
    AmendmentDiffEntry,
    BidDecisionSection,
    CapturePackage,
    CaptureStrategySection,
    ComplianceItem,
    ComplianceMatrixSection,
    CyberPostureSnapshot,
    CyberSection,
    DetectedAmendment,
    EvaluationSection,
    GovernanceReadinessSection,
    IncumbentSummary,
    KeyPersonRef,
    KeyPersonnelSection,
    OpportunitySection,
    PackageCompleteness,
    PassFailItem,
    PastPerformanceRef,
    PastPerformanceSection,
    QAEntry,
    QAHistorySection,
    RequirementItem,
    RequirementsMatrixSection,
    ScoredFactor,
    SolicitationSection,
    TeamingPartnerRef,
    TeamingPartnersSection,
    TenantRegistrationSection,
    WinStrategySection,
    to_iso,
)

log = logging.getLogger(__name__)

# Description excerpt cap — keeps the package compact while preserving
# enough context for a quick read by ProposalOS or a human reviewer.
DESCRIPTION_EXCERPT_CHARS = 4000

# Pattern for FAR/DFARS clause numbers commonly cited in cyber requirements.
# Examples:  FAR 52.204-21,  DFARS 252.204-7012,  DFARS 252.204-7019
CLAUSE_PATTERN = re.compile(
    r"\b(?:FAR|DFARS)\s+\d{2,3}\.\d{3}-\d{1,4}\b",
    re.IGNORECASE,
)

# CMMC level mention pattern.
CMMC_LEVEL_PATTERN = re.compile(
    r"\bCMMC\s*(?:Level\s*)?(?:2\.0\s*)?(?:Level\s*)?([123])\b",
    re.IGNORECASE,
)


class CodexClientProtocol:  # structural typing target
    async def get_sprs_by_clerk_org(self, clerk_org_id: str) -> Any: ...


class CapturePackageBuilder:
    """Assemble a Capture Package for one pursuit.

    Stateless aside from the injected session + Codex client. Safe to call
    repeatedly; each ``build()`` produces a fresh snapshot.
    """

    def __init__(
        self,
        session: AsyncSession,
        codex_client: CodexClientProtocol | None = None,
    ) -> None:
        self.session = session
        self.codex = codex_client

    async def build(
        self,
        *,
        tenant_id: UUID,
        pursuit_id: UUID,
    ) -> CapturePackage:
        pursuit, opportunity, tenant = await self._load_core(tenant_id, pursuit_id)

        enriched = await self._load_enriched(opportunity.id)
        brief = await self._load_brief(tenant_id, opportunity.id)
        score = await self._load_score(tenant_id, opportunity.id)
        questions = await self._load_questions(tenant_id, opportunity.id)
        founder_owner = await self._load_owner_founder(pursuit.owner_founder_id)

        opportunity_section = self._build_opportunity_section(opportunity)
        solicitation_section = await self._build_solicitation_section(opportunity)
        cyber_section = await self._build_cyber_section(opportunity, brief, tenant)
        capture_strategy = self._build_capture_strategy_section(brief, enriched)
        bid_decision = await self._build_bid_decision_section(
            pursuit, score, founder_owner
        )
        qa_section = self._build_qa_section(questions)

        past_performance = await self._build_past_performance_section(
            tenant_id, pursuit.id
        )
        key_personnel = await self._build_key_personnel_section(
            tenant_id, pursuit.id
        )
        teaming_partners = await self._build_teaming_partners_section(
            tenant_id, pursuit.id
        )

        compliance = await self._build_compliance_matrix_section(
            tenant_id, opportunity.id
        )
        requirements = await self._build_requirements_matrix_section(
            tenant_id, opportunity.id
        )
        evaluation = await self._build_evaluation_section(
            tenant_id, opportunity.id
        )
        win_strategy = WinStrategySection(
            win_themes=list(pursuit.win_themes or []),
            discriminators=list(pursuit.discriminators or []),
        )

        # GovernanceOS not yet wired, but CaptureOS already syncs set-asides
        # from SAM Entity. Populate that one field; the rest stay null and
        # source flips to "captureos_partial" so consumers know.
        set_asides = list(tenant.set_aside_certifications or [])
        governance = GovernanceReadinessSection(
            set_asides_held=set_asides,
            reps_certs_current=(
                tenant.sam_registration_status == "active"
                if tenant.sam_registration_status
                else None
            ),
            reps_certs_last_renewed_at=to_iso(tenant.sam_registration_date),
            source=("captureos_partial" if set_asides or tenant.sam_registration_status else "stub"),
        )

        tenant_registration = self._build_tenant_registration_section(tenant)

        completeness = self._compute_completeness(
            opportunity_section=opportunity_section,
            solicitation=solicitation_section,
            compliance=compliance,
            requirements=requirements,
            evaluation=evaluation,
            cyber=cyber_section,
            capture_strategy=capture_strategy,
            win_strategy=win_strategy,
            past_performance=past_performance,
            key_personnel=key_personnel,
            teaming_partners=teaming_partners,
            bid_decision=bid_decision,
            governance=governance,
            qa=qa_section,
            tenant_registration=tenant_registration,
        )

        return CapturePackage(
            generated_at=datetime.now(timezone.utc).isoformat(),
            tenant_id=str(tenant.id),
            tenant_slug=tenant.slug,
            pursuit_id=str(pursuit.id),
            opportunity=opportunity_section,
            solicitation=solicitation_section,
            compliance_matrix=compliance,
            requirements_matrix=requirements,
            evaluation=evaluation,
            cyber=cyber_section,
            capture_strategy=capture_strategy,
            win_strategy=win_strategy,
            past_performance=past_performance,
            key_personnel=key_personnel,
            teaming_partners=teaming_partners,
            bid_decision=bid_decision,
            governance_readiness=governance,
            tenant_registration=tenant_registration,
            qa_history=qa_section,
            completeness=completeness,
        )

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    async def _load_core(
        self, tenant_id: UUID, pursuit_id: UUID
    ) -> tuple[Pursuit, OpportunityRaw, Tenant]:
        pursuit = (
            await self.session.execute(
                select(Pursuit).where(
                    Pursuit.id == pursuit_id,
                    Pursuit.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if pursuit is None:
            raise PursuitNotFound(pursuit_id)

        opportunity = (
            await self.session.execute(
                select(OpportunityRaw).where(OpportunityRaw.id == pursuit.opportunity_id)
            )
        ).scalar_one_or_none()
        if opportunity is None:
            raise OpportunityMissing(pursuit.opportunity_id)

        tenant = (
            await self.session.execute(select(Tenant).where(Tenant.id == tenant_id))
        ).scalar_one()

        return pursuit, opportunity, tenant

    async def _load_enriched(
        self, opportunity_id: UUID
    ) -> OpportunityEnriched | None:
        return (
            await self.session.execute(
                select(OpportunityEnriched).where(
                    OpportunityEnriched.opportunity_id == opportunity_id
                )
            )
        ).scalar_one_or_none()

    async def _load_brief(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> OpportunityBrief | None:
        return (
            await self.session.execute(
                select(OpportunityBrief).where(
                    OpportunityBrief.tenant_id == tenant_id,
                    OpportunityBrief.opportunity_id == opportunity_id,
                )
            )
        ).scalar_one_or_none()

    async def _load_score(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> OpportunityScore | None:
        return (
            await self.session.execute(
                select(OpportunityScore).where(
                    OpportunityScore.tenant_id == tenant_id,
                    OpportunityScore.opportunity_id == opportunity_id,
                )
            )
        ).scalar_one_or_none()

    async def _load_questions(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> list[OpportunityQuestion]:
        return list(
            (
                await self.session.execute(
                    select(OpportunityQuestion)
                    .where(
                        OpportunityQuestion.tenant_id == tenant_id,
                        OpportunityQuestion.opportunity_id == opportunity_id,
                    )
                    .order_by(OpportunityQuestion.created_at.asc())
                )
            )
            .scalars()
            .all()
        )

    async def _load_owner_founder(
        self, founder_id: UUID | None
    ) -> Founder | None:
        if founder_id is None:
            return None
        return (
            await self.session.execute(
                select(Founder).where(Founder.id == founder_id)
            )
        ).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_opportunity_section(
        self, opp: OpportunityRaw
    ) -> OpportunitySection:
        excerpt: str | None = None
        if opp.description_text:
            excerpt = opp.description_text[:DESCRIPTION_EXCERPT_CHARS]

        return OpportunitySection(
            notice_id=opp.source_id,
            source=opp.source,
            solicitation_number=opp.solicitation_number,
            title=opp.title,
            notice_type=opp.notice_type,
            agency=opp.agency,
            subagency=opp.subagency,
            office=opp.office,
            naics_code=opp.naics_code,
            set_aside=opp.set_aside,
            contract_type=_extract_contract_type(opp.raw_payload),
            response_deadline=to_iso(opp.response_deadline),
            posted_at=to_iso(opp.posted_at),
            estimated_value_low=_decimal_to_float(opp.estimated_value_low),
            estimated_value_high=_decimal_to_float(opp.estimated_value_high),
            place_of_performance=opp.place_of_performance,
            submission_method=_extract_submission_method(opp.raw_payload),
            description_url=opp.description_url,
            description_text_excerpt=excerpt,
        )

    def _build_tenant_registration_section(
        self, tenant: Tenant
    ) -> TenantRegistrationSection:
        from datetime import date as date_t

        status = tenant.sam_registration_status or "unverified"
        # Match the eligibility endpoint's enum exactly.
        if status not in ("active", "expired", "invalid", "unverified"):
            status = "invalid"
        days_until = None
        if tenant.sam_registration_expires_at is not None:
            days_until = (
                tenant.sam_registration_expires_at - date_t.today()
            ).days

        # Mirror the eligibility endpoint's blocker list logic without
        # circular-importing the route module. Keep wording in sync if you
        # edit one, edit both.
        blockers: list[str] = []
        hard = False
        if not tenant.uei:
            blockers.append("No UEI on file. Add the company's UEI in Settings.")
            hard = True
        if tenant.is_excluded:
            blockers.append(
                f"Company appears on the federal exclusions list "
                f"({tenant.exclusions_record_count} record(s))."
            )
            hard = True
        if status == "expired":
            blockers.append("SAM.gov registration is EXPIRED.")
            hard = True
        elif status == "invalid":
            blockers.append("SAM.gov registration could not be verified.")
            hard = True
        elif status == "active" and days_until is not None and days_until <= 30:
            blockers.append(
                f"SAM.gov registration expires in {days_until} day(s)."
            )
        if not (tenant.set_aside_certifications or []):
            blockers.append("No set-aside certifications on file.")
        if tenant.sprs_score is None:
            blockers.append("No SPRS score on file (DFARS 7019/7020 risk).")

        return TenantRegistrationSection(
            uei=tenant.uei,
            cage_code=tenant.cage_code,
            sam_registration_status=status,  # type: ignore[arg-type]
            sam_registration_date=to_iso(tenant.sam_registration_date),
            sam_registration_expires_at=to_iso(tenant.sam_registration_expires_at),
            sam_days_until_expiration=days_until,
            sam_last_checked_at=to_iso(tenant.sam_registration_last_checked_at),
            is_excluded=tenant.is_excluded,
            exclusions_record_count=tenant.exclusions_record_count,
            exclusions_last_checked_at=to_iso(tenant.exclusions_last_checked_at),
            blockers=blockers,
            has_hard_blocker=hard,
        )

    async def _build_solicitation_section(
        self, opp: OpportunityRaw
    ) -> SolicitationSection:
        # V1: separate file-level ingestion not yet built (Section C of
        # CaptureOS_Requirements.md). The primary description URL is what
        # we expose today. ``detected_amendments`` carries any system-
        # detected content changes since first ingestion.
        amendment_rows = (
            await self.session.execute(
                select(OpportunityAmendment)
                .where(OpportunityAmendment.opportunity_id == opp.id)
                .order_by(OpportunityAmendment.detected_at.desc())
            )
        ).scalars().all()
        detected = [
            DetectedAmendment(
                id=str(a.id),
                detected_at=a.detected_at.isoformat(),
                fields_changed=[entry.get("field", "") for entry in (a.diff_summary or [])],
                diff=[
                    AmendmentDiffEntry(
                        field=entry.get("field", ""),
                        before=entry.get("before"),
                        after=entry.get("after"),
                    )
                    for entry in (a.diff_summary or [])
                ],
                previous_response_deadline=to_iso(a.previous_response_deadline),
                new_response_deadline=to_iso(a.new_response_deadline),
            )
            for a in amendment_rows
        ]

        return SolicitationSection(
            primary_description_url=opp.description_url,
            primary_description_text_excerpt=(
                opp.description_text[:DESCRIPTION_EXCERPT_CHARS]
                if opp.description_text
                else None
            ),
            files=[],
            amendments=[],
            detected_amendments=detected,
            raw_payload_available=bool(opp.raw_payload),
        )

    async def _build_cyber_section(
        self,
        opp: OpportunityRaw,
        brief: OpportunityBrief | None,
        tenant: Tenant,
    ) -> CyberSection:
        haystack_parts: list[str] = []
        if opp.description_text:
            haystack_parts.append(opp.description_text)
        if brief is not None:
            haystack_parts.append(brief.scope_one_sentence)
            haystack_parts.extend(brief.must_have_requirements or [])
            haystack_parts.extend(brief.nice_to_have or [])
        haystack = "\n".join(p for p in haystack_parts if p)

        clauses = sorted({m.upper().replace("  ", " ") for m in CLAUSE_PATTERN.findall(haystack)})
        cmmc_match = CMMC_LEVEL_PATTERN.search(haystack)
        cmmc_required = f"Level {cmmc_match.group(1)}" if cmmc_match else None

        handles_cui = "CUI" in haystack or "Controlled Unclassified Information" in haystack
        handles_fci = "FCI" in haystack or "Federal Contract Information" in haystack
        handles_itar = "ITAR" in haystack

        snapshot = await self._fetch_cyber_posture(tenant)
        sufficiency, notes = self._compare_posture(
            posture=snapshot,
            cmmc_required=cmmc_required,
            clauses=clauses,
        )

        return CyberSection(
            clauses_identified=clauses,
            cmmc_level_required=cmmc_required,
            handles_cui=handles_cui or None,
            handles_fci=handles_fci or None,
            handles_itar=handles_itar or None,
            posture_snapshot=snapshot,
            sufficiency=sufficiency,
            sufficiency_notes=notes,
        )

    async def _fetch_cyber_posture(
        self, tenant: Tenant
    ) -> CyberPostureSnapshot | None:
        if self.codex is None or not tenant.clerk_org_id:
            return None
        try:
            posture = await self.codex.get_sprs_by_clerk_org(tenant.clerk_org_id)
        except Exception as exc:  # never let Codex outage break the package
            log.warning("codex sprs fetch failed: %s", exc)
            return None
        if posture is None:
            return None
        return CyberPostureSnapshot(
            sprs_score=getattr(posture, "score", None),
            sprs_max=getattr(posture, "max", None) or getattr(posture, "max_score", None),
            sprs_assessment_date=to_iso(getattr(posture, "assessment_date", None)),
            sprs_source_url=getattr(posture, "source_url", None),
            cmmc_level_current=getattr(posture, "cmmc_level", None),
            source="codex",
            snapshot_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _compare_posture(
        *,
        posture: CyberPostureSnapshot | None,
        cmmc_required: str | None,
        clauses: list[str],
    ) -> tuple[str, str | None]:
        if posture is None:
            if cmmc_required or clauses:
                return (
                    "unknown",
                    "Solicitation cites cyber clauses but no Codex posture snapshot is available.",
                )
            return "unknown", None
        if cmmc_required and posture.cmmc_level_current:
            if posture.cmmc_level_current.lower() >= cmmc_required.lower():
                return "sufficient", None
            return (
                "gap",
                f"Solicitation requires {cmmc_required}; current Codex posture is "
                f"{posture.cmmc_level_current}.",
            )
        return "unknown", None

    def _build_capture_strategy_section(
        self,
        brief: OpportunityBrief | None,
        enriched: OpportunityEnriched | None,
    ) -> CaptureStrategySection:
        incumbent: IncumbentSummary | None = None
        if enriched is not None and enriched.incumbent_name:
            incumbent = IncumbentSummary(
                name=enriched.incumbent_name,
                uei=enriched.incumbent_uei,
                contract_id=enriched.incumbent_contract_id,
                end_date=to_iso(enriched.incumbent_end_date),
                award_amount=_decimal_to_float(enriched.incumbent_award_amount),
            )

        if brief is None:
            return CaptureStrategySection(incumbent=incumbent)

        return CaptureStrategySection(
            scope_one_sentence=brief.scope_one_sentence,
            incumbent=incumbent,
            must_have_requirements=brief.must_have_requirements or [],
            nice_to_have=brief.nice_to_have or [],
            red_flags_for_small_biz=brief.red_flags_for_small_biz or [],
            suggested_team_roles=brief.suggested_team_roles or [],
        )

    async def _build_bid_decision_section(
        self,
        pursuit: Pursuit,
        score: OpportunityScore | None,
        founder: Founder | None,
    ) -> BidDecisionSection:
        # Prefer the structured bid_decision column. Fall back to inferring
        # from stage so legacy pursuits (created before 0024) still produce
        # a reasonable section.
        decision: str = pursuit.bid_decision
        if decision == "pending":
            if pursuit.stage in ("submit", "won", "lost"):
                decision = "bid"
            elif pursuit.stage in ("pursue", "propose"):
                decision = "bid"
            # else: stay "pending"

        score_breakdown: dict[str, Any] | None = None
        score_value: int | None = None
        if score is not None:
            score_value = score.score
            raw_breakdown = getattr(score, "breakdown", None) or getattr(
                score, "score_breakdown", None
            )
            if isinstance(raw_breakdown, dict):
                score_breakdown = raw_breakdown

        # Use structured bid_decided_at when set, falling back to last
        # stage change for the inferred path.
        decided_at = pursuit.bid_decided_at or pursuit.last_stage_change_at

        decider_user_id_str: str | None = None
        if pursuit.bid_decided_by_user_id is not None:
            user = (
                await self.session.execute(
                    select(User).where(User.id == pursuit.bid_decided_by_user_id)
                )
            ).scalar_one_or_none()
            if user is not None:
                decider_user_id_str = str(user.id)

        # Prefer the structured bid_rationale; fall back to notes.
        rationale = pursuit.bid_rationale or pursuit.notes

        return BidDecisionSection(
            decision=decision,  # type: ignore[arg-type]
            pursuit_stage=pursuit.stage,
            decided_at=to_iso(decided_at),
            decider_user_id=decider_user_id_str,
            decider_founder_slug=founder.slug if founder else None,
            rationale=rationale,
            score=score_value,
            score_breakdown=score_breakdown,
        )

    def _build_qa_section(
        self, questions: list[OpportunityQuestion]
    ) -> QAHistorySection:
        return QAHistorySection(
            entries=[
                QAEntry(
                    id=str(q.id),
                    question=q.question,
                    answer=q.answer,
                    submitted_at=to_iso(q.created_at),
                    answered_at=to_iso(q.created_at),
                    starter_kind=q.starter_kind,
                )
                for q in questions
            ]
        )

    async def _build_past_performance_section(
        self, tenant_id: UUID, pursuit_id: UUID
    ) -> PastPerformanceSection:
        library_size = (
            await self.session.execute(
                select(func.count())
                .select_from(PastPerformance)
                .where(PastPerformance.tenant_id == tenant_id)
            )
        ).scalar_one()

        rows = list(
            (
                await self.session.execute(
                    select(PastPerformance, PursuitPastPerformance)
                    .join(
                        PursuitPastPerformance,
                        PursuitPastPerformance.past_performance_id
                        == PastPerformance.id,
                    )
                    .where(PursuitPastPerformance.pursuit_id == pursuit_id)
                    .order_by(PursuitPastPerformance.sort_order.asc())
                )
            ).all()
        )
        selected = [
            PastPerformanceRef(
                id=str(pp.id),
                title=pp.title,
                customer_agency=pp.customer_agency,
                customer_office=pp.customer_office,
                contract_number=pp.contract_number,
                role=link.role or pp.role,
                period_start=to_iso(pp.period_start),
                period_end=to_iso(pp.period_end),
                contract_value=_decimal_to_float(pp.contract_value),
                summary=pp.summary,
                keywords=list(pp.keywords or []),
            )
            for pp, link in rows
        ]
        return PastPerformanceSection(
            selected=selected,
            library_size=int(library_size),
            selection_method="manual" if selected else "none",
        )

    async def _build_key_personnel_section(
        self, tenant_id: UUID, pursuit_id: UUID
    ) -> KeyPersonnelSection:
        library_size = (
            await self.session.execute(
                select(func.count())
                .select_from(Founder)
                .where(Founder.tenant_id == tenant_id)
            )
        ).scalar_one()

        rows = list(
            (
                await self.session.execute(
                    select(Founder, PursuitKeyPersonnel)
                    .join(
                        PursuitKeyPersonnel,
                        PursuitKeyPersonnel.founder_id == Founder.id,
                    )
                    .where(PursuitKeyPersonnel.pursuit_id == pursuit_id)
                    .order_by(PursuitKeyPersonnel.sort_order.asc())
                )
            ).all()
        )
        selected = [
            KeyPersonRef(
                id=str(f.id),
                slug=f.slug,
                full_name=f.full_name,
                title=link.role or f.title,
                pillar=f.pillar,
                bio=f.bio,
                email=f.email,
                areas_of_expertise=list(f.areas_of_expertise or []),
            )
            for f, link in rows
        ]
        return KeyPersonnelSection(
            selected=selected, library_size=int(library_size)
        )

    async def _load_extraction(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> SolicitationExtraction | None:
        return (
            await self.session.execute(
                select(SolicitationExtraction).where(
                    SolicitationExtraction.tenant_id == tenant_id,
                    SolicitationExtraction.opportunity_id == opportunity_id,
                )
            )
        ).scalar_one_or_none()

    async def _build_compliance_matrix_section(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> ComplianceMatrixSection:
        extraction = await self._load_extraction(tenant_id, opportunity_id)
        if extraction is None:
            return ComplianceMatrixSection()

        rows = list(
            (
                await self.session.execute(
                    select(ComplianceMatrixItem)
                    .where(ComplianceMatrixItem.extraction_id == extraction.id)
                    .order_by(ComplianceMatrixItem.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        items = [
            ComplianceItem(
                id=row.item_id,
                statement=row.statement,
                section_l_citation=row.section_l_citation,
                pass_fail=row.pass_fail,
                notes=row.notes,
            )
            for row in rows
        ]

        status_value = _matrix_status(extraction, has_items=bool(items))
        return ComplianceMatrixSection(
            items=items,
            source_documents=["opportunity.description_text"] if items else [],
            last_generated_at=to_iso(extraction.updated_at),
            status=status_value,  # type: ignore[arg-type]
        )

    async def _build_evaluation_section(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> EvaluationSection:
        extraction = await self._load_extraction(tenant_id, opportunity_id)
        if extraction is None:
            return EvaluationSection()

        pass_fail_rows = list(
            (
                await self.session.execute(
                    select(EvaluationPassFailItem)
                    .where(EvaluationPassFailItem.extraction_id == extraction.id)
                    .order_by(EvaluationPassFailItem.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        scored_rows = list(
            (
                await self.session.execute(
                    select(EvaluationScoredFactor)
                    .where(EvaluationScoredFactor.extraction_id == extraction.id)
                    .order_by(EvaluationScoredFactor.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )

        pass_fail = [
            PassFailItem(
                statement=row.statement,
                source_citation=row.source_citation,
            )
            for row in pass_fail_rows
        ]
        scored = [
            ScoredFactor(
                name=row.name,
                weight=float(row.weight) if row.weight is not None else None,
                description=row.description,
                source_citation=row.source_citation,
            )
            for row in scored_rows
        ]

        # An extraction exists, so call it "extracted" unless the
        # extraction itself is stale (amendment landed after the run).
        if extraction.status == "stale":
            status_value: str = "not_extracted"
        else:
            status_value = "extracted" if (pass_fail or scored) else "not_extracted"
        return EvaluationSection(
            pass_fail_items=pass_fail,
            scored_factors=scored,
            status=status_value,  # type: ignore[arg-type]
        )

    async def _build_requirements_matrix_section(
        self, tenant_id: UUID, opportunity_id: UUID
    ) -> RequirementsMatrixSection:
        extraction = await self._load_extraction(tenant_id, opportunity_id)
        if extraction is None:
            return RequirementsMatrixSection()

        rows = list(
            (
                await self.session.execute(
                    select(RequirementMatrixItem)
                    .where(RequirementMatrixItem.extraction_id == extraction.id)
                    .order_by(RequirementMatrixItem.sort_order.asc())
                )
            )
            .scalars()
            .all()
        )
        items = [
            RequirementItem(
                id=row.item_id,
                statement=row.statement,
                source_citation=row.source_citation,
                category=row.category,  # type: ignore[arg-type]
            )
            for row in rows
        ]

        status_value = _matrix_status(extraction, has_items=bool(items))
        return RequirementsMatrixSection(
            items=items,
            last_generated_at=to_iso(extraction.updated_at),
            status=status_value,  # type: ignore[arg-type]
        )

    async def _build_teaming_partners_section(
        self, tenant_id: UUID, pursuit_id: UUID
    ) -> TeamingPartnersSection:
        library_size = (
            await self.session.execute(
                select(func.count())
                .select_from(TeamingPartner)
                .where(TeamingPartner.tenant_id == tenant_id)
            )
        ).scalar_one()

        rows = list(
            (
                await self.session.execute(
                    select(TeamingPartner, PursuitTeamingPartner)
                    .join(
                        PursuitTeamingPartner,
                        PursuitTeamingPartner.teaming_partner_id == TeamingPartner.id,
                    )
                    .where(PursuitTeamingPartner.pursuit_id == pursuit_id)
                    .order_by(PursuitTeamingPartner.sort_order.asc())
                )
            ).all()
        )
        selected = [
            TeamingPartnerRef(
                id=str(p.id),
                name=p.name,
                uei=p.uei,
                cage_code=p.cage_code,
                capabilities=list(p.capabilities or []),
                naics_codes=list(p.naics_codes or []),
                set_aside_certifications=list(p.set_aside_certifications or []),
                contact_name=p.contact_name,
                contact_email=p.contact_email,
            )
            for p, _link in rows
        ]
        return TeamingPartnersSection(
            selected=selected, library_size=int(library_size)
        )

    # ------------------------------------------------------------------
    # Completeness reporting
    # ------------------------------------------------------------------

    def _compute_completeness(
        self,
        *,
        opportunity_section: OpportunitySection,
        solicitation: SolicitationSection,
        compliance: ComplianceMatrixSection,
        requirements: RequirementsMatrixSection,
        evaluation: EvaluationSection,
        cyber: CyberSection,
        capture_strategy: CaptureStrategySection,
        win_strategy: WinStrategySection,
        past_performance: PastPerformanceSection,
        key_personnel: KeyPersonnelSection,
        teaming_partners: TeamingPartnersSection,
        bid_decision: BidDecisionSection,
        governance: GovernanceReadinessSection,
        qa: QAHistorySection,
        tenant_registration: TenantRegistrationSection,
    ) -> PackageCompleteness:
        complete: list[str] = []
        partial: list[str] = []
        missing: list[str] = []
        gaps: list[str] = []

        # Opportunity is essentially always complete if we got this far.
        complete.append("opportunity")

        if solicitation.files or solicitation.amendments:
            complete.append("solicitation")
        elif solicitation.primary_description_url or solicitation.primary_description_text_excerpt:
            partial.append("solicitation")
            gaps.append(
                "Solicitation: only the primary description is available. "
                "File-level ingest (Section C of requirements doc) is not yet built."
            )
        else:
            missing.append("solicitation")
            gaps.append("Solicitation: no description URL or text available.")

        if compliance.status == "stale":
            partial.append("compliance_matrix")
            gaps.append(
                "Compliance matrix is STALE — opportunity was amended after "
                "the last extraction. Re-run extraction to capture the new "
                "Section L."
            )
        elif compliance.items:
            complete.append("compliance_matrix")
        elif compliance.status == "generated":
            partial.append("compliance_matrix")
            gaps.append(
                "Compliance matrix extracted but yielded no items — likely "
                "the description text is too thin (Section L lives in attached PDFs). "
                "Re-run after file ingest is built."
            )
        else:
            missing.append("compliance_matrix")
            gaps.append(
                "Compliance matrix not generated yet. POST "
                "/opportunities/{id}/solicitation-extraction to generate."
            )

        if requirements.status == "stale":
            partial.append("requirements_matrix")
            gaps.append(
                "Requirements matrix is STALE — opportunity was amended "
                "after the last extraction."
            )
        elif requirements.items:
            complete.append("requirements_matrix")
        elif requirements.status == "generated":
            partial.append("requirements_matrix")
            gaps.append(
                "Requirements matrix extracted but yielded no items — same "
                "cause as compliance matrix above."
            )
        else:
            missing.append("requirements_matrix")
            gaps.append(
                "Requirements matrix not generated yet. POST "
                "/opportunities/{id}/solicitation-extraction to generate."
            )

        if solicitation.detected_amendments:
            gaps.append(
                f"Opportunity has {len(solicitation.detected_amendments)} "
                f"detected amendment(s) since first ingest. Review on the "
                f"opportunity detail page."
            )

        if evaluation.pass_fail_items or evaluation.scored_factors:
            complete.append("evaluation")
        elif evaluation.status == "extracted":
            partial.append("evaluation")
            gaps.append(
                "Evaluation extracted but yielded no items — Section M likely "
                "lives in attached PDFs. Re-run after file ingest is built."
            )
        else:
            missing.append("evaluation")
            gaps.append(
                "Section M evaluation factors not extracted yet. POST "
                "/opportunities/{id}/solicitation-extraction to generate."
            )

        if cyber.posture_snapshot is not None:
            complete.append("cyber")
        elif cyber.clauses_identified:
            partial.append("cyber")
            gaps.append("Cyber clauses detected, but no Codex posture snapshot.")
        else:
            partial.append("cyber")

        if capture_strategy.scope_one_sentence or capture_strategy.incumbent:
            complete.append("capture_strategy")
        else:
            partial.append("capture_strategy")
            gaps.append("Capture strategy: brief and incumbent intel not yet generated.")

        if win_strategy.win_themes or win_strategy.discriminators:
            complete.append("win_strategy")
        else:
            missing.append("win_strategy")
            gaps.append(
                "Win themes and discriminators not captured yet. Edit on "
                "the pursuit detail page."
            )

        if past_performance.selected:
            complete.append("past_performance")
        elif past_performance.library_size > 0:
            partial.append("past_performance")
            gaps.append(
                f"Past performance: {past_performance.library_size} entries in library, "
                "none selected for this pursuit yet."
            )
        else:
            missing.append("past_performance")
            gaps.append("Past performance library is empty.")

        if key_personnel.selected:
            complete.append("key_personnel")
        elif key_personnel.library_size > 0:
            partial.append("key_personnel")
            gaps.append(
                f"Key personnel: {key_personnel.library_size} founders/people in library, "
                "none selected for this pursuit yet."
            )
        else:
            missing.append("key_personnel")
            gaps.append("Key personnel library is empty.")

        if teaming_partners.selected:
            complete.append("teaming_partners")
        elif teaming_partners.library_size > 0:
            partial.append("teaming_partners")
            gaps.append(
                f"Teaming partners: {teaming_partners.library_size} in library, "
                "none selected for this pursuit yet."
            )
        else:
            partial.append("teaming_partners")

        if bid_decision.decision == "bid":
            complete.append("bid_decision")
        elif bid_decision.decision == "no_bid":
            complete.append("bid_decision")
        else:
            partial.append("bid_decision")
            gaps.append(f"Bid decision still pending (stage={bid_decision.pursuit_stage}).")

        if governance.source == "governance_os":
            complete.append("governance_readiness")
        elif governance.source == "captureos_partial":
            partial.append("governance_readiness")
            gaps.append(
                "Governance readiness is partial: set-asides + reps & certs "
                "currency from SAM, but FCL / accounting / E-Verify need "
                "GovernanceOS (Integration Contract #2)."
            )
        else:
            missing.append("governance_readiness")
            gaps.append(
                "GovernanceOS readiness facts feed not wired up yet (Integration Contract #2)."
            )

        if tenant_registration.has_hard_blocker:
            missing.append("tenant_registration")
            gaps.append(
                "TENANT REGISTRATION HARD BLOCKER — bidding must not proceed "
                "until resolved: " + "; ".join(tenant_registration.blockers[:3])
            )
        elif tenant_registration.blockers:
            partial.append("tenant_registration")
            gaps.append(
                "Tenant registration warnings: "
                + "; ".join(tenant_registration.blockers[:3])
            )
        else:
            complete.append("tenant_registration")

        if qa.entries:
            complete.append("qa_history")
        else:
            partial.append("qa_history")

        total = len(complete) + len(partial) + len(missing)
        # Heuristic: complete=1.0, partial=0.5, missing=0.0
        weighted = len(complete) + 0.5 * len(partial)
        overall_pct = round((weighted / total) * 100, 1) if total else 0.0

        return PackageCompleteness(
            overall_pct=overall_pct,
            sections_complete=complete,
            sections_partial=partial,
            sections_missing=missing,
            gaps=gaps,
        )


class PursuitNotFound(Exception):
    def __init__(self, pursuit_id: UUID) -> None:
        super().__init__(f"pursuit {pursuit_id} not found in this tenant")
        self.pursuit_id = pursuit_id


class OpportunityMissing(Exception):
    def __init__(self, opportunity_id: UUID) -> None:
        super().__init__(
            f"pursuit references opportunity {opportunity_id} which is missing"
        )
        self.opportunity_id = opportunity_id


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _matrix_status(
    extraction: SolicitationExtraction, *, has_items: bool
) -> str:
    """Translate a SolicitationExtraction.status + item count to the
    Capture Package matrix-section status enum.

    The DB enum is ``pending | running | complete | failed | stale``;
    the Capture Package enum is ``not_generated | generated | stale``.
    """
    if extraction.status == "stale":
        return "stale"
    if has_items:
        return "generated"
    return "not_generated"


def _extract_contract_type(raw_payload: dict[str, Any] | None) -> str | None:
    if not raw_payload:
        return None
    # SAM.gov keys vary; check the common ones without being prescriptive.
    for key in ("typeOfContractPricing", "contractType", "contract_type"):
        v = raw_payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _extract_submission_method(raw_payload: dict[str, Any] | None) -> str | None:
    if not raw_payload:
        return None
    for key in ("submissionMethod", "submission_method", "responseSubmission"):
        v = raw_payload.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None
