"""DB-decoupled decision inputs.

Everything the decision engine needs, assembled from detection + enrichment +
config, but with no ORM dependency so the engine (and its golden fixtures) are
pure unit tests. The scoring/decision worker builds this from the DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Set-aside families (mirror scoring.py).
SDVOSB_CODES = frozenset({"SDVOSBC", "SDVOSBS", "VSA", "VSS"})
SMALL_BIZ_CODES = frozenset({"SBA", "SBP", "SB"})

# Early-stage notice types that make an opportunity a shaping candidate.
EARLY_STAGE_NOTICE_TYPES = frozenset(
    {
        "Sources Sought",
        "Presolicitation",
        "Special Notice",
        "Request for Information",
        "RFI",
    }
)


@dataclass(frozen=True)
class DeliveryCapacity:
    prime_value_min: float = 25_000
    prime_value_max: float = 2_000_000
    subcontract_value_min: float = 50_000
    subcontract_value_max: float = 3_000_000
    core_people: int = 4
    max_ft_without_partner: int = 5


@dataclass(frozen=True)
class DecisionInputs:
    # --- eligibility ---
    set_aside: str | None = None
    tenant_set_aside_codes: frozenset[str] = field(
        default_factory=lambda: SDVOSB_CODES | SMALL_BIZ_CODES
    )
    scan_unrestricted: bool = True

    # --- timing ---
    response_deadline: date | None = None
    as_of: date | None = None
    notice_type: str | None = None

    # --- signals (summarized from detection.SignalReport) ---
    has_direct_cyber: bool = False
    has_frcs_ot: bool = False
    has_training: bool = False
    has_facility_adjacency: bool = False
    has_construction_context: bool = False
    relevance_weight: int = 0  # sum of positive weights across relevant families
    has_page_evidence: bool = False

    # --- barriers (disqualifier gate_codes detected) ---
    hard_barriers: frozenset[str] = frozenset()
    soft_barriers: frozenset[str] = frozenset()

    # --- value / scale ---
    estimated_value_high: float | None = None
    naics_is_construction: bool = False

    # --- incumbent / exclusions (bug-fix input) ---
    incumbent_excluded: bool | None = None
    has_incumbent: bool = False

    # --- teaming ---
    prime_targets_count: int = 0

    # --- package completeness (from opportunities_raw.documents_status) ---
    completeness: str = "metadata_only"

    # --- priors ---
    legacy_pursuit_model: str | None = None
    sdvosb_certified: bool = True

    # --- config ---
    capacity: DeliveryCapacity = field(default_factory=DeliveryCapacity)

    # ---- derived helpers ----
    @property
    def is_early_stage(self) -> bool:
        return (self.notice_type or "") in EARLY_STAGE_NOTICE_TYPES

    @property
    def set_aside_eligible(self) -> bool:
        """Eligible to prime on set-aside grounds: no set-aside, an unrestricted
        notice we scan, or a set-aside in the tenant's certs."""
        if not self.set_aside:
            return True
        code = self.set_aside.upper()
        if code in {c.upper() for c in self.tenant_set_aside_codes}:
            return True
        # Unrestricted / full-and-open markers.
        return code in {"NONE", "", "UNRESTRICTED", "FULL"}

    @property
    def has_sub_work_package(self) -> bool:
        """A bounded cyber/FRCS work package MacTech could own as a sub. Direct
        cyber counts too — MacTech can sub its cyber scope under a prime even
        when it can't prime the vehicle/scope itself."""
        return self.has_frcs_ot or self.has_facility_adjacency or self.has_direct_cyber

    @property
    def has_any_relevant_scope(self) -> bool:
        return (
            self.has_direct_cyber
            or self.has_frcs_ot
            or self.has_training
            or self.has_facility_adjacency
        )
