# Capture Data Contracts

Reference for the data contracts that the MacTech CaptureOS capture-engine
overhaul introduced across Slices 1-4. This is the shape other code codes
against: the Pydantic interchange types, the new database entities, the
evidence contract that ties every conclusion back to a source, and the
versioning contract that makes every decision reproducible.

This document records what is **built** as of Slices 1-4. Where a contract is
reserved for Slice 5 (LLM adjudication), it is called out explicitly and marked
**planned**. Field lists here are transcribed from the source files cited in
each section; if the code and this document disagree, the code wins and this
document is stale — fix it.

Design invariants that govern the whole layer:

- **Deterministic core.** The signal detector, the gates, and the decision
  engine are pure and LLM-free. Golden fixtures pin their output. The LLM layer
  (Slice 5) may explain a gate but can never overrule it.
- **DB-decoupled engine.** The decision engine consumes a plain dataclass
  (`DecisionInputs`), not ORM rows, so it unit-tests without a database.
- **Everything traces to evidence.** No conclusion exists without a citation
  back to a document, page/section, signal, gate, or award.
- **Everything is versioned.** Every persisted decision stamps the formula and
  knowledge-pack versions that produced it, plus a snapshot of its inputs.

---

## 1. Pydantic schemas

### 1.1 Decision interchange types — `decision/schemas.py`

These are the persisted shapes (mirrored by the DB tables in §2) and the
interchange types other systems consume. They are Pydantic so that any future
LLM-produced decision fragment validates against the same contract.

`FORMULA_VERSION = "1.0.0"` — the semantic version of the deterministic decision
formula. Stamped onto every `LaneDecision` and persisted on every decision-vector
row. Bump it whenever the vector math, gate logic, or lane selection changes in
a way that would move a score.

**`EvidenceCitation`** — a pointer back to the evidence a claim rests on.

| Field | Type | Notes |
|---|---|---|
| `kind` | `str` | `"signal"` \| `"gate"` \| `"document"` \| `"award"` |
| `label` | `str` | Human-readable label for the cited thing |
| `document_id` | `str \| None` | Source document, when applicable |
| `page_number` | `int \| None` | Page anchor |
| `section_heading` | `str \| None` | Section anchor |
| `snippet` | `str \| None` | The quoted evidence text |

**`GateRecord`** — the interchange form of one deterministic gate result.

| Field | Type | Notes |
|---|---|---|
| `gate_code` | `str` | e.g. `EXPIRED`, `INELIGIBLE_SET_ASIDE` |
| `status` | `str` | `pass` \| `fail` \| `unknown` \| `waived` |
| `severity` | `str` | `hard` \| `soft` |
| `reason_code` | `str \| None` | Maps to a `NO_BID_REASON_CODES` value |
| `detail` | `str` | Free-text explanation (default `""`) |
| `source` | `str` | Default `"deterministic"`; also `"exclusions_cache"` |

**`DecisionVector`** — the nine scored dimensions, every one an `int` in `[0, 100]`
(`Field(ge=0, le=100, default=0)`).

| Field | Meaning |
|---|---|
| `relevance_score` | How much MacTech-relevant scope the notice carries |
| `prime_fit_score` | Fit for MacTech to prime |
| `subcontract_fit_score` | Fit for MacTech to sub a bounded work package |
| `winability_score` | Odds of winning (set-aside edge, recompete signal, early stage) |
| `deliverability_score` | Can MacTech actually deliver (barriers, scale) |
| `strategic_value_score` | Strategic weight (FRCS/OT, direct cyber, teaming) |
| `urgency_score` | Days-to-deadline pressure |
| `evidence_completeness_score` | How complete the analyzed package is |
| `overall_priority_score` | Lane-weighted rollup; the headline sort key |

`overall_priority_score` is not a tenth independent dimension — it is computed
from the other eight via a lane-specific weight profile (see §1.4) and then
capped for `NO_BID` (≤15) and `WATCH` (≤45).

**`LaneDecision`** — the top-level decision object.

| Field | Type | Notes |
|---|---|---|
| `pursuit_lane` | `PursuitLane` | One of the seven lanes (§1.2) |
| `reason_codes` | `list[str]` | `NO_BID_REASON_CODES` values (default `[]`) |
| `confidence` | `str` | `low` \| `medium` \| `high` (default `medium`) |
| `lane_weight_profile` | `str` | `prime` \| `sub` (default `prime`) |
| `formula_version` | `str` | Defaults to `FORMULA_VERSION` |
| `vector` | `DecisionVector` | The nine dimensions |
| `gates` | `list[GateRecord]` | Every evaluated gate (default `[]`) |
| `evidence` | `list[EvidenceCitation]` | Supporting citations (default `[]`) |

### 1.2 Lanes and reason codes — `decision/lanes.py`

**`PursuitLane`** is a `Literal` of seven values; `PURSUIT_LANES` is the tuple of
the same values in order:

| Lane | Meaning |
|---|---|
| `PRIME_NOW` | Eligible, unblocked, in capacity, MacTech-primeable scope |
| `PRIME_WITH_PARTNER` | Primeable + eligible, blocked only by a partner-fillable gap |
| `SUB_TO_IDENTIFIED_PRIME` | Bounded work package under a known prime target |
| `SUB_TO_PRIME_NOT_YET_IDENTIFIED` | Bounded work package, prime not yet found |
| `SHAPE_EARLY` | Early-stage notice we can influence, with real scope |
| `WATCH` | Relevant but not yet actionable |
| `NO_BID` | Hard-gated out, or no real MacTech scope |

**`NO_BID_REASON_CODES`** — the 16 structured reasons a pursuit is declined. Used
as `LaneDecision.reason_codes` and `GateRecord.reason_code`.

```
INELIGIBLE_SET_ASIDE     VEHICLE_UNAVAILABLE      SCOPE_TOO_LARGE
STAFFING_UNREALISTIC     PAST_PERFORMANCE_GAP     MANDATORY_LICENSE_GAP
MANDATORY_CLEARANCE_GAP  BONDING_GAP              GEOGRAPHIC_MISMATCH
DEADLINE_UNWORKABLE      NO_REAL_MACTECH_SCOPE    LOW_MARGIN_COMMODITY
OEM_RESTRICTION          DUPLICATE                EXPIRED
OTHER
```

**`LegacyPursuitModel`** — a `Literal` of the eight legacy cyber_scope
`PursuitModel` values, kept populated for back-compat:
`NO_ACTION`, `WATCHLIST`, `PRIME_PURSUE`, `SUBCONTRACTOR_PURSUE`,
`CYBER_SUPPORT_ONLY`, `FRCS_OT_SPECIALIST`, `CMMC_COMPLIANCE_SUPPORT`,
`CLARIFICATION_REQUIRED`.

**`lane_from_legacy_model(model)`** produces a coarse **prior** lane from the
legacy detector's recommendation, before the gates and decision vector refine
it. It is never authoritative on its own. Mapping:

| Legacy model | Prior lane |
|---|---|
| `NO_ACTION`, `WATCHLIST` | `WATCH` |
| `CLARIFICATION_REQUIRED` | `SHAPE_EARLY` |
| `PRIME_PURSUE`, `CMMC_COMPLIANCE_SUPPORT`, `CYBER_SUPPORT_ONLY` | `PRIME_NOW` |
| `SUBCONTRACTOR_PURSUE`, `FRCS_OT_SPECIALIST` | `SUB_TO_PRIME_NOT_YET_IDENTIFIED` |
| anything else / unknown | `WATCH` (default) |

### 1.3 Engine input — `decision/facts.py`

**`DecisionInputs`** is a frozen dataclass: everything the engine needs, with no
ORM dependency. The scoring/decision worker builds it from detection +
enrichment + config; the golden fixtures build it by hand.

| Field | Type | Default | Group |
|---|---|---|---|
| `set_aside` | `str \| None` | `None` | eligibility |
| `tenant_set_aside_codes` | `frozenset[str]` | `SDVOSB_CODES \| SMALL_BIZ_CODES` | eligibility |
| `scan_unrestricted` | `bool` | `True` | eligibility |
| `response_deadline` | `date \| None` | `None` | timing |
| `as_of` | `date \| None` | `None` | timing |
| `notice_type` | `str \| None` | `None` | timing |
| `has_direct_cyber` | `bool` | `False` | signals |
| `has_frcs_ot` | `bool` | `False` | signals |
| `has_training` | `bool` | `False` | signals |
| `has_facility_adjacency` | `bool` | `False` | signals |
| `has_construction_context` | `bool` | `False` | signals |
| `relevance_weight` | `int` | `0` | signals |
| `has_page_evidence` | `bool` | `False` | signals |
| `hard_barriers` | `frozenset[str]` | `frozenset()` | barriers |
| `soft_barriers` | `frozenset[str]` | `frozenset()` | barriers |
| `estimated_value_high` | `float \| None` | `None` | value/scale |
| `naics_is_construction` | `bool` | `False` | value/scale |
| `incumbent_excluded` | `bool \| None` | `None` | incumbent/exclusions |
| `has_incumbent` | `bool` | `False` | incumbent/exclusions |
| `prime_targets_count` | `int` | `0` | teaming |
| `completeness` | `str` | `"metadata_only"` | package completeness |
| `legacy_pursuit_model` | `str \| None` | `None` | priors |
| `sdvosb_certified` | `bool` | `True` | priors |
| `capacity` | `DeliveryCapacity` | `DeliveryCapacity()` | config |

**`DeliveryCapacity`** (frozen dataclass) — MacTech's delivery envelope:
`prime_value_min=25_000`, `prime_value_max=2_000_000`,
`subcontract_value_min=50_000`, `subcontract_value_max=3_000_000`,
`core_people=4`, `max_ft_without_partner=5`.

Module constants: `SDVOSB_CODES = {SDVOSBC, SDVOSBS, VSA, VSS}`,
`SMALL_BIZ_CODES = {SBA, SBP, SB}`, and `EARLY_STAGE_NOTICE_TYPES`
(`Sources Sought`, `Presolicitation`, `Special Notice`,
`Request for Information`, `RFI`).

**Derived properties** (computed, not stored):

| Property | Rule |
|---|---|
| `is_early_stage` | `notice_type` is in `EARLY_STAGE_NOTICE_TYPES` |
| `set_aside_eligible` | No set-aside, an unrestricted marker (`NONE`/`""`/`UNRESTRICTED`/`FULL`), or a set-aside in the tenant's certs |
| `has_sub_work_package` | `has_frcs_ot` or `has_facility_adjacency` or `has_direct_cyber` (direct cyber can be subbed under a prime) |
| `has_any_relevant_scope` | `has_direct_cyber` or `has_frcs_ot` or `has_training` or `has_facility_adjacency` |

### 1.4 Engine output — `decision/engine.py`

**`DecisionResult`** is the engine's native dataclass; `decide(inputs)` returns
it. `to_lane_decision()` projects it onto the persisted `LaneDecision`.

| Field | Type | Notes |
|---|---|---|
| `pursuit_lane` | `PursuitLane` | The one authoritative lane |
| `reason_codes` | `list[str]` | `NO_BID_REASON_CODES` when declined |
| `vector` | `DecisionVector` | Nine dimensions |
| `gates` | `list[Gate]` | Native `Gate` objects (§3) |
| `confidence` | `str` | `low` \| `medium` \| `high` |
| `lane_weight_profile` | `str` | `prime` \| `sub` |
| `needs_human_review` | `bool` | Low confidence or an `INCOMPLETE_PACKAGE` gate |
| `legacy_pursuit_model` | `str \| None` | Carried prior (default `None`) |
| `evidence_note` | `str` | Default `""` |
| `extras` | `dict` | Default `{}` |

`to_lane_decision()` copies lane, reason_codes, confidence, lane_weight_profile,
`formula_version=FORMULA_VERSION`, and the vector, and maps each native `Gate`
into a `GateRecord`. The `overall_priority_score` weight profiles are:

- **prime**: `0.25·relevance + 0.25·prime_fit + 0.20·winability +
  0.20·deliverability + 0.10·strategic_value`
- **sub**: `0.25·relevance + 0.30·subcontract_fit + 0.15·winability +
  0.15·deliverability + 0.15·strategic_value`

Hard gates override the weighted vector; `NO_BID` caps overall at 15 and `WATCH`
caps it at 45.

### 1.5 Signal detection — `detection/signals.py`

**`SignalHit`** (frozen dataclass) — one evidence-bearing detection.

| Field | Type | Notes |
|---|---|---|
| `concept_id` | `str` | Knowledge-pack concept id |
| `family` | `str` | Concept family |
| `evidence_category` | `str \| None` | e.g. `ufc_frcs`, `far_dfars_cmmc` |
| `canonical_name` | `str` | Concept canonical name |
| `normalized_term` | `str` | Normalized match term |
| `weight` | `int` | Positive relevance weight |
| `negative_weight` | `int` | Negative weight |
| `disqualifier` | `bool` | Whether this hit is a barrier |
| `gate_code` | `str \| None` | Gate raised when disqualifier |
| `severity` | `str \| None` | `hard` \| `soft` for disqualifiers |
| `match_type` | `str` | `REGEX` \| `LITERAL` \| `IDENTIFIER` |
| `snippet` | `str` | Surrounding text |
| `start` | `int` | Char offset (start) |
| `end` | `int` | Char offset (end) |

**`SignalReport`** collects the hits plus identifiers and the pack version.

| Field | Type |
|---|---|
| `hits` | `list[SignalHit]` (default `[]`) |
| `identifiers` | `list[IdentifierHit]` (default `[]`) |
| `pack_version` | `str` (default `""`) |

Accessor properties / methods, which are exactly what feeds the boolean signal
flags on `DecisionInputs`:

| Accessor | Result |
|---|---|
| `by_family` | `dict[str, list[SignalHit]]` grouped by family |
| `disqualifiers` | Hits where `disqualifier` is true |
| `families_present()` | Set of families seen |
| `has_family(family)` | Any hit in that family |
| `has_direct_cyber` | Any hit in `{rmf_ato_emass, nist_cnssi_fips, far_dfars_cmmc, direct_cyber}` |
| `has_frcs_ot` | Any hit in `{ufc_frcs, ot_ics_scada_pit}` |
| `has_facility_adjacency` | Any hit in `{facility_adjacency}` |
| `has_training` | Any hit in `{training}` |
| `has_acquisition_context` | Any hit in `{acquisition_context}` |
| `relevance_weight` | Sum of `weight` over non-disqualifier hits |
| `barriers_by_severity()` | `(hard_gate_codes, soft_gate_codes)` frozensets from disqualifiers |

### 1.6 Identifiers — `detection/identifiers.py`

**`IdentifierHit`** (frozen dataclass) — a normalized UFGS spec number or DFARS
clause. `find_identifiers(text)` collapses the many written variants to one
canonical form so the detector and knowledge pack agree on identity.

| Field | Type | Notes |
|---|---|---|
| `kind` | `str` | `"ufgs"` \| `"dfars"` |
| `canonical` | `str` | e.g. `25 05 11`, `252.204-7012` |
| `raw` | `str` | The matched surface text |
| `start` | `int` | Char offset (start) |
| `end` | `int` | Char offset (end) |

### 1.7 Knowledge pack — `knowledge/pack.py`

**`Concept`** (frozen dataclass) — one capture concept in the versioned pack.

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` | — | Concept id |
| `family` | `str` | — | Family (from the YAML file) |
| `canonical_name` | `str` | — | Display name |
| `evidence_category` | `str \| None` | — | Drives the `SignalReport` accessors |
| `normalized_term` | `str` | — | Falls back to canonical name |
| `aliases` | `tuple[str, ...]` | `()` | Literal match variants |
| `abbreviations` | `tuple[str, ...]` | `()` | Literal match variants |
| `exact_phrases` | `tuple[str, ...]` | `()` | Literal match variants |
| `regex` | `str \| None` | `None` | Regex match (overrides literals) |
| `related_concepts` | `tuple[str, ...]` | `()` | Cross-links |
| `positive_weight` | `int` | `0` | Relevance contribution |
| `negative_weight` | `int` | `0` | Negative contribution |
| `disqualifier` | `bool` | `False` | Barrier flag |
| `gate_code` | `str \| None` | `None` | Gate raised when disqualifier |
| `severity` | `str \| None` | `None` | `hard` \| `soft` for disqualifiers |
| `ufgs` | `str \| None` | `None` | Associated UFGS section |
| `ufgs_tier` | `int \| None` | `None` | UFGS tier |
| `source_ref` | `str \| None` | `None` | Provenance |
| `effective_date` | `date \| None` | `None` | Activation date (as-of filtered) |
| `enabled` | `bool` | `True` | Disabled concepts are skipped |

`Concept.match_patterns` is a computed property: canonical name plus every alias,
abbreviation, and exact phrase, deduped and order-preserving, used by the matcher
when no regex is set.

**`KnowledgePack`** (frozen dataclass):

| Field | Type | Notes |
|---|---|---|
| `versions` | `dict[str, str]` | family → version |
| `concepts` | `tuple[Concept, ...]` | All enabled, as-of-effective concepts |
| `blocks` | `dict[str, dict[str, Any]]` | Non-concept structured blocks by family |

`pack_version` (property) joins `versions` as a sorted `";"`-delimited
`family=version` string — this exact string is what gets persisted as
`knowledge_pack_version` (see §5). Helpers: `by_family`, `by_evidence_category`,
`by_id`, `disqualifiers`, `block(family, name, default)`. Module-level
`pack_version(pack_dir=None)` returns the same string for the loaded pack.

### 1.8 Planned — Slice 5 LLM adjudication schemas

Not yet built. The following Pydantic schemas are reserved for the Slice 5 LLM
adjudication layer and will follow the same evidence-ID validation pattern as the
deterministic contracts (see §4.3):

- `OpportunityAnalysis`
- `WorkPackageAnalysis`
- `PrimeTargetRecommendation`
- `AdjudicationResult`

Each will require that every claim cite only evidence IDs supplied to the model;
a Pydantic validator drops claims that cite an unknown id. The LLM may explain or
enrich a deterministic conclusion but never overrule a hard gate.

---

## 2. Database entities

Two isolation regimes apply. **SHARED** tables carry no `tenant_id` — the
procurement package is a property of the notice, not a tenant, so it is fetched
and parsed once (following the `opportunities_enriched` / `awards_history`
precedent). **Tenant-scoped** tables carry a `tenant_id` FK to `tenants` with
`ondelete=CASCADE` and are queried only via `scoped_session`; that tenant filter
is the isolation guard until RLS lands (RLS deferred).

### 2.1 `opportunity_documents` — SHARED (Slice 2)

One row per distinct binary, keyed by content hash. Re-fetching an unchanged file
is a no-op; a changed file is a new row that supersedes the old. Defined in
`models/opportunity_document.py`, created in migration `0039_opportunity_documents`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `opportunity_id` | UUID FK → `opportunities_raw` (CASCADE) | not null |
| `source_url` | String(2048) | nullable |
| `filename` | String(512) | nullable |
| `doc_class` | String(48) | default `'other'` |
| `content_hash` | String(64) | not null; reprocess key |
| `storage_key` | String(1024) | nullable |
| `mime_type` | String(128) | nullable |
| `doc_format` | String(16) | nullable |
| `byte_size` | BigInteger | nullable |
| `page_count` | Integer | nullable |
| `extracted_char_count` | Integer | default `0` |
| `ocr_used` | Boolean | default `false` |
| `archived_from` | String(1024) | parent archive key when unzipped; else null |
| `status` | String(24) | default `'not_discovered'`; one of `DOCUMENT_STATUSES` |
| `error` | Text | nullable |
| `fetched_at` | TIMESTAMPTZ | nullable |
| `reprocessed_at` | TIMESTAMPTZ | nullable |
| `created_at` | TIMESTAMPTZ | `now()` |
| `updated_at` | TIMESTAMPTZ | `now()`, on-update |

**`UNIQUE(opportunity_id, content_hash)`** (`uq_opportunity_documents_opp_hash`)
is the reprocess key: identity is (notice, byte content), so an unchanged
re-fetch upserts onto the same row and a changed file lands as a distinct row.
Index `ix_opportunity_documents_opp` on `opportunity_id`.

**`DOCUMENT_STATUSES`** (processing lifecycle, stored as String(24)):

```
not_discovered  queued  downloaded  parsed  partially_parsed
access_restricted  unsupported  failed_retryable  failed_permanent
```

### 2.2 `document_sections` — SHARED (Slice 2)

Page/section provenance that the detector cites as evidence. Defined in
`models/opportunity_document.py`, created in `0039`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `document_id` | UUID FK → `opportunity_documents` (CASCADE) | not null |
| `opportunity_id` | UUID FK → `opportunities_raw` (CASCADE) | not null; denormalized for opp-scoped evidence queries without a join |
| `ordinal` | Integer | default `0`; section order |
| `page_number` | Integer | nullable |
| `section_heading` | String(255) | nullable |
| `section_path` | String(255) | nullable |
| `char_start` | Integer | default `0`; offset into concatenated doc text |
| `char_end` | Integer | default `0`; offset into concatenated doc text |
| `text` | Text | nullable |
| `created_at` | TIMESTAMPTZ | `now()` |

Indexes: `ix_document_sections_document` on `document_id`,
`ix_document_sections_opp` on `opportunity_id`. The `char_start` / `char_end`
offsets are the stable evidence anchors described in §4.

### 2.3 `opportunity_decision_vectors` — tenant-scoped (Slice 4)

One authoritative decision per `(tenant, opportunity)`, recomputed on input
change and versioned for reproducibility. Defined in `models/decision.py`,
created in `0040_decision_engine`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `tenant_id` | UUID FK → `tenants` (CASCADE) | not null |
| `opportunity_id` | UUID FK → `opportunities_raw` (CASCADE) | not null |
| `relevance_score` | Integer | default `0` |
| `prime_fit_score` | Integer | default `0` |
| `subcontract_fit_score` | Integer | default `0` |
| `winability_score` | Integer | default `0` |
| `deliverability_score` | Integer | default `0` |
| `strategic_value_score` | Integer | default `0` |
| `urgency_score` | Integer | default `0` |
| `evidence_completeness_score` | Integer | default `0` |
| `overall_priority_score` | Integer | default `0` |
| `pursuit_lane` | String(40) | not null |
| `reason_codes` | JSONB | default `'[]'` |
| `confidence` | String(8) | default `'medium'` |
| `lane_weight_profile` | String(16) | default `'prime'` |
| `needs_human_review` | Boolean | default `false` |
| `formula_version` | String(16) | nullable; versioning |
| `knowledge_pack_version` | String(128) | nullable; versioning |
| `inputs_snapshot` | JSONB | default `'{}'`; versioning/reproducibility |
| `manual_lane_override` | String(40) | nullable; manual override |
| `override_note` | Text | nullable; manual override |
| `computed_at` | TIMESTAMPTZ | `now()` |
| `updated_at` | TIMESTAMPTZ | `now()`, on-update |

`UNIQUE(tenant_id, opportunity_id)` (`uq_decision_vectors_tenant_opp`) — one row
per tenant/opportunity, upserted on recompute. Indexes: `ix_decision_vectors_opp`
on `opportunity_id`, `ix_decision_vectors_lane` on `(tenant_id, pursuit_lane)`.

### 2.4 `opportunity_gates` — tenant-scoped (Slice 4)

One deterministic gate result — inspectable, waivable, auditable. Defined in
`models/decision.py`, created in `0040`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `tenant_id` | UUID FK → `tenants` (CASCADE) | not null |
| `opportunity_id` | UUID FK → `opportunities_raw` (CASCADE) | not null |
| `gate_code` | String(48) | not null |
| `status` | String(12) | not null; one of `GATE_STATUSES` |
| `severity` | String(8) | not null; one of `GATE_SEVERITIES` |
| `reason_code` | String(48) | nullable |
| `detail` | Text | nullable |
| `evidence` | JSONB | default `'{}'`; structured evidence |
| `source` | String(24) | default `'deterministic'` |
| `waived_by_id` | UUID FK → `users` (SET NULL) | nullable |
| `detected_at` | TIMESTAMPTZ | `now()` |

`UNIQUE(tenant_id, opportunity_id, gate_code)` (`uq_gates_tenant_opp_code`).
Index `ix_gates_opp` on `opportunity_id`. Enums:
`GATE_STATUSES = (pass, fail, unknown, waived)`,
`GATE_SEVERITIES = (hard, soft)`.

### 2.5 Mirror columns on `opportunity_scores` (Slice 4)

Two new denormalized columns added to `opportunity_scores` in `0040`, defined in
`models/scoring.py`:

| Column | Type | Notes |
|---|---|---|
| `overall_priority_score` | Integer | nullable |
| `pursuit_lane` | String(40) | nullable |

The authoritative source for both is `opportunity_decision_vectors`. They are
mirrored here so that list/sort views stay single-table (no join to the decision
table for the common "rank this tenant's opportunities" query). They are
**written in the same transaction** as the decision-vector upsert to avoid
drift, and are null until the decision engine has run for that
`(tenant, opportunity)`.

### 2.6 New columns on ingestion / opportunity tables

Both in `models/opportunity.py`.

- **`ingestion_state.metrics`** (JSONB, nullable) — added in migration
  `0038_ingestion_metrics`. One state row per query-family job; holds the last
  run's `{examined, matched, inserted, updated, pages, posted_from, posted_to}`.
  Purely observational — nothing keys on it — so the retrieval families stay
  tunable from the knowledge-pack YAML without code changes.
- **`opportunities_raw.documents_status`** (JSONB, nullable) — added in `0039`.
  Package-completeness summary:
  `{completeness, discovered, downloaded, parsed, failed, restricted,
  unsupported}`. `completeness` is one of `PACKAGE_COMPLETENESS`. Null until the
  generalized fetcher has run. This is the field the decision engine reads into
  `DecisionInputs.completeness`.

**`PACKAGE_COMPLETENESS`** (what the current analysis is based on):

```
metadata_only  description_only  partial_attachments  all_accessible
```

The engine's completeness ladder scores these `20 / 40 / 60 / 90` respectively
(unknown values fall back to `20`).

### 2.7 Migration summary

| Revision | Down-revision | Adds |
|---|---|---|
| `0038_ingestion_metrics` | `0037_bid_invite_seen_watermark` | `ingestion_state.metrics` (JSONB) |
| `0039_opportunity_documents` | `0038_ingestion_metrics` | `opportunity_documents`, `document_sections` (both SHARED), `opportunities_raw.documents_status` |
| `0040_decision_engine` | `0039_opportunity_documents` | `opportunity_decision_vectors`, `opportunity_gates` (both tenant-scoped), mirror columns on `opportunity_scores` |

---

## 3. The evidence contract

Every conclusion the capture engine produces must be traceable back to the
source text that supports it. The contract is layered:

1. **Detections carry document coordinates.** The legacy `DetectionResult`
   (`cyber_scope/schemas.py`) carries `page_number`, `section_heading`, and
   `document_name` alongside `term`, `normalized_term`, `category`, `weight`,
   `match_type`, `surrounding_text`, `ufgs`, and `ufgs_tier`. The new
   `SignalHit` (`detection/signals.py`) carries `snippet` plus `start` / `end`
   char offsets and the `concept_id` / `evidence_category` that name the concept
   matched.

2. **Sections are the stable anchors.** `document_sections` rows hold
   `char_start` / `char_end` offsets into the JOIN-concatenated document text.
   Because the concatenation order is deterministic (documents joined, sections
   in `ordinal` order), those offsets are stable anchors: a `SignalHit`'s
   `start`/`end` resolves to a section, and the section resolves to a
   `page_number` / `section_heading` / `document_id`. That chain is what an
   `EvidenceCitation` records.

3. **Gates carry structured evidence.** Each `opportunity_gates` row has an
   `evidence` JSONB column (default `{}`) capturing the structured basis for the
   gate — the values that tripped it — so a `fail` is inspectable and waivable
   rather than opaque.

The rule: no score, lane, or gate exists without a citation path back to a
document coordinate. `EvidenceCitation` (§1.1) is the serialized form of that
path.

### 3.3 Planned — Slice 5 evidence-ID contract

Not yet built. When the LLM adjudication layer lands, evidence handed to the
model will be addressed by a deterministic id:

```
evidence_id = "ev:" + sha1(doc_hash + section_ordinal + term)[:10]
```

The model receives a set of evidence blocks each tagged with its `evidence_id`,
and every claim it returns must cite only ids from that set. A Pydantic
validator on the Slice 5 schemas (§1.8) drops any claim that cites an unknown id,
so a hallucinated citation cannot enter the record. This keeps the LLM layer
inside the same "everything traces to evidence" invariant as the deterministic
core.

---

## 4. The versioning contract

Every persisted decision record is reproducible: it stamps the versions of the
logic and vocabulary that produced it, plus a snapshot of its inputs.

Every `opportunity_decision_vectors` row stamps:

| Column | Source | Meaning |
|---|---|---|
| `formula_version` | `decision/schemas.py` `FORMULA_VERSION` (currently `"1.0.0"`) | Version of the deterministic vector + gate + lane logic |
| `knowledge_pack_version` | `knowledge.pack.pack_version()` | The sorted `";"`-joined `family=version` string for the loaded pack |
| `inputs_snapshot` | The `DecisionInputs` used | JSONB snapshot making the decision reproducible without re-deriving inputs |

For **LLM-produced records (Slice 5, planned)**, the same rows will additionally
carry `prompt_version` and `model_version`, so an adjudicated conclusion records
not only the deterministic formula and pack but the exact prompt template and
model that generated it.

`inputs_snapshot` is the reproducibility keystone: given the snapshot plus the
stamped `formula_version` and `knowledge_pack_version`, `decide()` re-runs to the
same `DecisionResult`. A version bump on either axis is what justifies (and
explains) a recompute that moves a score.

---

## 5. Cross-references

| Concern | File |
|---|---|
| Decision interchange schemas | `packages/intelligence/src/mactech_intelligence/decision/schemas.py` |
| Lanes + reason codes + legacy mapping | `.../decision/lanes.py` |
| Engine inputs + derived properties | `.../decision/facts.py` |
| Gates | `.../decision/gates.py` |
| Engine (`decide`, `DecisionResult`) | `.../decision/engine.py` |
| Signal detector | `.../detection/signals.py` |
| Identifier normalization | `.../detection/identifiers.py` |
| Knowledge pack loader | `.../knowledge/pack.py` |
| Legacy detection result | `.../cyber_scope/schemas.py` |
| Document / section models | `packages/db/src/mactech_db/models/opportunity_document.py` |
| Decision vector / gate models | `.../models/decision.py` |
| Score mirror columns | `.../models/scoring.py` |
| Ingestion / opportunity columns | `.../models/opportunity.py` |
| Migrations | `packages/db/alembic/versions/0038_ingestion_metrics.py`, `0039_opportunity_documents.py`, `0040_decision_engine.py` |
