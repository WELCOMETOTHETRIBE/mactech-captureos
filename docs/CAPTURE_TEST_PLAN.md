# CaptureOS Capture-Engine Test Plan

**Scope:** The capture-engine overhaul (Slices 1–4) — knowledge-pack extraction,
document toolkit, multi-family signal detection, and the pursuit-lane decision
engine. This document records the tests that are **actually built and passing on
HEAD**, the golden fixtures that pin lane behavior, the regression and shadow-run
strategy that protects those fixtures from silent drift, and the known gaps that
still need coverage.

This is a documentation artifact. It describes the test surface; it does not
change it.

**Status legend used below**

- **Built** — test exists in the repo today and passes.
- **Planned** — named here as the next coverage step; not yet written.
- **Known-red** — a pre-existing failing test unrelated to this overhaul (see §9).

---

## 1. Test architecture at a glance

The capture engine is layered so that the parts most likely to be wrong — the
gates and the lane classification — are the parts that are pure functions of
their inputs and therefore trivially testable without a database, network, or
LLM.

| Layer | Package | Purity | Test file(s) |
|---|---|---|---|
| Knowledge pack (concepts, families, playbooks) | `packages/intelligence` | Pure data load | `test_knowledge_pack.py`, `test_query_families.py`, `test_dictionary_adapter_parity.py` |
| Document toolkit (extract, classify, archive, store) | `apps/workers` | Pure (in-memory blobs, `tmp_path` store) | `test_documents_toolkit.py` |
| Signal detection (identifiers, families, disqualifiers) | `packages/intelligence` | Pure text -> report | `test_detection.py` |
| Decision engine (gates, vector, lane) | `packages/intelligence` | Pure `DecisionInputs` -> `LaneDecision` | `test_decision_engine.py` |
| Decision COMPUTE worker (DB glue) | `apps/workers` | Integration (live DB) | **Planned** |

The decision engine takes a DB-decoupled `DecisionInputs` value object rather
than a database row. That decoupling is the single most important design choice
for testability: every fixture in §2 is a hand-built `DecisionInputs`, so the
tests are fast, deterministic, and reviewable by a non-engineer reading the
scenario names.

---

## 2. Golden fixtures — the 12 canonical scenarios

Source: `packages/intelligence/tests/test_decision_engine.py` (brief §21).

Twelve scenarios pin the lane classification, the hard gates, and the scoring
vector. Each row below is a real test in the file; the assertions column lists
exactly what the test checks, not a paraphrase. Common inputs across fixtures:
`as_of = 2026-07-16`, `SOON = as_of + 10 days`, `PAST = as_of − 5 days`.

| # | Scenario | Key inputs | Expected lane | Additional assertions |
|---|---|---|---|---|
| 1 | Small SDVOSB CMMC readiness | `set_aside=SDVOSBC`, `has_direct_cyber`, value `150k`, `all_accessible`, page evidence | `PRIME_NOW` | `vector.prime_fit_score >= 60` |
| 2 | Cyber tabletop + AAR | `set_aside=SBA`, `has_direct_cyber`, value `90k`, `all_accessible` | `PRIME_NOW` | — |
| 3 | Broad enterprise SOC above prime capacity | `set_aside=SDVOSBC`, `has_direct_cyber`, value `2.5M` | `PRIME_WITH_PARTNER` | `SCOPE_TOO_LARGE` in `reason_codes` |
| 4 | $50M design-build, UFGS 25 05 11, primes identified | `has_frcs_ot`, construction context + NAICS, value `50M`, `prime_targets_count=3`, hard barrier `BONDING_GAP` | `SUB_TO_IDENTIFIED_PRIME` | `lane_weight_profile == "sub"` |
| 5 | HVAC/BAS/BACnet, no explicit cyber phrase | `has_facility_adjacency`, construction context + NAICS, value `8M`, `description_only` | `SUB_TO_PRIME_NOT_YET_IDENTIFIED` | `lane != NO_BID` (must **not** be discarded) |
| 6 | Construction, no networked controls | construction NAICS + context, value `5M`, no cyber signal | `NO_BID` | `NO_REAL_MACTECH_SCOPE` in `reason_codes` |
| 7 | Expired but relevant | `set_aside=SDVOSBC`, `has_direct_cyber`, `response_deadline=PAST` | `NO_BID` | `EXPIRED` in `reason_codes` |
| 8 | Mandatory vehicle-holder task order | `has_direct_cyber`, value `1M`, hard barrier `VEHICLE_UNAVAILABLE` | sub path only | lane **not** in `{PRIME_NOW, PRIME_WITH_PARTNER}`; lane in `{SUB_TO_IDENTIFIED_PRIME, SUB_TO_PRIME_NOT_YET_IDENTIFIED}` |
| 9 | Restricted / missing attachments | `has_direct_cyber`, `completeness=metadata_only` | (gate-driven) | `needs_human_review is True`; `confidence == "low"`; `evidence_completeness_score <= 40`; an `INCOMPLETE_PACKAGE` gate present |
| 10 | Amendment adds cyber scope, near deadline | `has_direct_cyber`, deadline `as_of + 2 days`, `all_accessible` | `PRIME_NOW` | `vector.urgency_score >= 85` |
| 11 | False-positive CUI (unrelated grant) | `notice_type=Grant`, no cyber signal, value `500k` | `NO_BID` | `vector.relevance_score == 0` |
| 12 | Division 25 spec, real FRCS deliverables + page evidence | `has_frcs_ot`, construction context + NAICS, page evidence, value `12M`, `prime_targets_count=0` | `SUB_TO_PRIME_NOT_YET_IDENTIFIED` | `relevance_score >= 55`; `evidence_completeness_score >= 80` |

### 2.1 What the fixtures collectively guarantee

- **Prime vs. sub routing** is driven by scope size and vehicle/bonding
  barriers, not just by cyber relevance. Fixtures 1–3 walk the prime capacity
  ceiling (150k and 90k prime; 2.5M forces a partner). Fixtures 4, 8, and 12
  cover the three ways a strong opportunity is pushed to a sub lane: primes
  already identified (4), a hard barrier that blocks prime self-performance
  (8), and prime-not-yet-identified with no barrier (12).
- **"Investigate, don't discard"** for facility-adjacent work with no explicit
  cyber phrase (fixture 5) is the hidden-scope case: HVAC/BAS/BACnet keeps the
  opportunity alive in a sub lane instead of dropping it. Fixture 6 is the
  control — construction with genuinely no networked controls correctly goes
  `NO_BID`.
- **Hard gates are terminal.** Expiry (7) and false-positive relevance (11)
  both yield `NO_BID` regardless of how attractive the rest of the record looks.
- **Incompleteness degrades confidence rather than guessing** (fixture 9):
  a metadata-only package trips `INCOMPLETE_PACKAGE`, flags human review, and
  caps completeness at 40.

---

## 3. Cross-cutting guards (same file)

Beyond the 12 scenarios, `test_decision_engine.py` carries three structural
guards:

### 3.1 Hard gate overrides an attractive vector
`test_hard_gate_overrides_attractive_vector` builds a deliberately attractive
record — SDVOSB set-aside, direct cyber, FRCS/OT, page evidence, full
completeness — but expired. The assertion is that `NO_BID` still wins and
`vector.overall_priority_score <= 15`. This is the priority-inversion guard: no
combination of positive signals may resurrect a hard-gated opportunity.

### 3.2 Lane decision serialization
`test_lane_decision_serializes` calls `result.to_lane_decision().model_dump()`
and asserts the dumped payload preserves `pursuit_lane` and a nested
`vector.relevance_score`. This protects the on-the-wire contract that the
COMPUTE worker persists and the API returns.

### 3.3 Evidence-completeness ladder (20 / 40 / 60 / 90)
`test_evidence_completeness_ladder` is parametrized over the four completeness
tiers and pins the exact score for each:

| `completeness` input | `evidence_completeness_score` |
|---|---|
| `metadata_only` | 20 |
| `description_only` | 40 |
| `partial_attachments` | 60 |
| `all_accessible` | 90 |

These four numbers are load-bearing: fixtures 9 and 12 assert against the
`<= 40` and `>= 80` boundaries, so any change to the ladder ripples into the
golden set and fails loudly (see §7).

---

## 4. Test inventory by slice

### Slice 1 — Knowledge pack + retrieval families
Files: `test_knowledge_pack.py`, `test_query_families.py`,
`test_dictionary_adapter_parity.py`.

**`test_knowledge_pack.py`** exercises the pack loader:
- `test_pack_loads_all_families` — asserts all eight families are present:
  `cyber_services`, `frcs_ot`, `construction_systems`, `clauses_frameworks`,
  `acquisition_signals`, `agency_offices`, `disqualifiers`,
  `pursuit_playbooks`.
- `test_pack_version_is_stamped` — the pack version string carries per-family
  stamps (`frcs_ot=…`, `cyber_services=…`).
- `test_every_concept_has_required_fields` — every concept has an id, canonical
  name, normalized term, and family, and `match_patterns[0]` equals the
  canonical name.
- `test_legacy_concepts_map_to_known_categories` — exactly **34** concepts map
  to legacy evidence categories (the parity anchor; see the Slice 1 parity test
  below).
- `test_disqualifiers_carry_gate_codes` — every disqualifier carries a
  `gate_code` and is **not** a legacy detector category.
- `test_pursuit_playbooks_cover_every_lane` — a playbook exists and is non-empty
  for all seven lanes, including `SHAPE_EARLY` and `WATCH`.

**`test_query_families.py`** covers the retrieval-side family builder:
- five families present (`family_a_direct_cyber` … `family_e_early_stage`);
- pipeline B (`family_c_facility_construction`) leads with broad construction
  NAICS (236220, 237310, 238210, 541330) and requires **no** cyber language at
  the API — recall-first;
- the NAICS union across families is de-duplicated;
- family groups merge into the SAM query groups (legacy `ufgs_shortlist` still
  resolves, and every family key is addressable);
- `early_stage` notice types include `Sources Sought`.

**`test_dictionary_adapter_parity.py` — the exact-parity regression guard.**
This is the keystone of Slice 1. The knowledge pack was extracted from the
legacy `data/cyber_scope_dictionary.yml`. The parity test asserts the
pack-backed `load_dictionary()` reproduces the legacy YAML **byte-for-byte**,
comparing the full key tuple `(category, term, normalized_term, weight, regex,
aliases)` for every term and asserting equal length. It also checks
`load_construction_signals()` equals the legacy list and that passing an
explicit path still loads the original file. As long as this test is green, the
cyber_scope detector is provably unchanged by the extraction — the pack is a
faithful relocation, not a rewrite.

### Slice 2 — Document toolkit
File: `apps/workers/tests/test_documents_toolkit.py` (pure; no DB or network).

- **Format detection + extraction** — TXT, HTML (tag/script stripping), CSV,
  XLSX (via `openpyxl`, `importorskip`), and the negative case that a ZIP is
  not treated as extractable text (`doc.ok is False`, `doc.format == "zip"`).
  PDF and DOCX paths are part of the same `extract_text`/`detect_format`
  surface.
- **Safe archive expansion** (`expand_archive`) — the security surface:
  - members are flattened and path components stripped (traversal defense);
  - traversal entries (`../../evil.txt`) keep only the basename, executables
    (`payload.exe`) are dropped, benign files pass;
  - too-many-members raises `ArchiveError` at `MAX_MEMBERS + 1`;
  - nested-archive depth beyond the limit (outer→mid→inner = depth 3, limit 2)
    raises `ArchiveError`;
  - `is_zip` sniffs by content, not extension.
- **Classification** (`classify_document`) — parametrized filename/text ->
  type: PWS, statement_of_work, section_l, section_m, wage_determination,
  amendment, `ufgs_specification` (recognized from body text
  "SECTION 25 05 11 …"), and the `other` fallback.
- **Sections / provenance** (`build_sections`) — page numbers are 1-based,
  headings are captured, and every section's `[char_start:char_end]` slice into
  the JOIN-concatenated body reproduces the original page text exactly. This is
  the offset-alignment invariant that lets page evidence be cited back to a
  precise span.
- **Object store** (`FilesystemDocumentStore`) — content-addressed key
  round-trips (`put`/`get`/`exists`), keys are stable and content-addressed, and
  a traversal key (`../../etc/passwd`) raises `ValueError`.

### Slice 3 — Multi-family signal detection
File: `packages/intelligence/tests/test_detection.py`.

- **Identifier normalization** — UFGS variants (`UFGS 25 05 11`, hyphenated
  `25-05-11`, bare-with-context `see 25 05 11`, and the extended
  `25 08 11.00 20`) all normalize to canonical form; DFARS variants including an
  **en-dash** (`252.204–7012`) normalize to `252.204-7012`. Direct helpers
  `canonical_ufgs`/`canonical_dfars` are checked too.
- **Bare-six-digit false-positive guard** —
  `test_bare_six_digits_not_a_false_ufgs` asserts a bare `250511` with no
  separators or context word is **not** a UFGS hit. This is the guard against
  spurious UFGS matches on invoice numbers and the like.
- **Multi-family detection** — CMMC/SSP/POA&M direct-cyber concepts;
  DFARS 252.204-7019/7020 + SPRS surfacing the `clauses_frameworks` family.
- **Facility-adjacency-without-cyber-phrase** — the hidden-scope detector: an
  HVAC/BACnet/central-plant-controls blurb with no explicit cyber word still
  surfaces a `construction_systems` or `frcs_ot` family and a concrete concept
  (`central_plant_controls` or `bacnet`). This is the detection-layer partner to
  decision fixture 5.
- **Disqualifier gate codes** — a Top Secret clearance + bonding blurb carries
  `MANDATORY_CLEARANCE_GAP` and `BONDING_GAP` gate codes.
- **False-positive CUI** — a generic "protect CUI per policy" grant sentence
  does **not** light up delivery signals (`cmmc`, `rmf`,
  `security_controls_assessment`). Detection-layer partner to decision
  fixture 11.
- **Version stamp** — the report carries a `pack_version` containing
  `cyber_services=…`, so every detection result is traceable to the pack it ran
  against.

### Slice 4 — Decision engine
File: `packages/intelligence/tests/test_decision_engine.py`. Fully described in
§2 and §3.

---

## 5. Coverage targets

- **Business logic: ≥ 70% line coverage** (scoring, ingestion, compliance/
  detection), per the project standard.
- **Gates and lane classification: materially higher.** The decision engine is a
  pure function of `DecisionInputs`, and the 12 golden fixtures plus three
  cross-cutting guards exercise every lane, every hard gate, and the full
  completeness ladder. This is the highest-value code in the engine and it is
  effectively fully fixture-covered.
- **Detection and document toolkit** carry dedicated pure-function suites
  (§4, Slices 2–3) covering the security-sensitive archive paths and the
  identifier false-positive guards explicitly.

### Current gaps (tracked, not hidden)

- **API-route tests: absent (pre-existing).** No coverage of the HTTP surface
  that returns lane decisions. Predates this overhaul.
- **Frontend tests: absent (pre-existing).** No component or integration tests
  on the web app.
- **Decision COMPUTE worker: uncovered.**
  `apps/workers/src/mactech_workers/tasks/decision.py` is integration glue that
  hydrates a `DecisionInputs` from the database, calls the (fully tested) pure
  engine, and persists the `LaneDecision`. The pure core is covered; the DB
  hydration/persistence path is not yet exercised by a live-DB test. This is the
  single highest-priority planned test (see §8).

---

## 6. Regression strategy

Three mechanisms defend the engine against silent behavior change.

### 6.1 Adapter-parity test as the knowledge-pack regression guard
`test_dictionary_adapter_parity.py` (§4, Slice 1) is the tripwire for the pack
extraction. Any edit to the knowledge pack that would change a term's category,
weight, regex, or aliases relative to the legacy dictionary breaks parity and
fails the build. The pack may grow (new families, new concepts), but the 34
relocated legacy terms are pinned identical. Pair this with
`test_legacy_concepts_map_to_known_categories`, which pins the count at exactly
34 — an accidental relocation of an extra term into a legacy category also fails.

### 6.2 Golden-fixture drift alerts
The 12 fixtures plus the completeness ladder are the behavioral contract of the
decision engine. Because they assert exact lanes, exact reason codes, and exact
scores, any change to a knowledge-pack weight or a scoring formula that **flips a
fixture's lane or moves a boundary score** fails the corresponding test by name.
The failure is loud and specific: the test name says which scenario changed
(e.g. `test_fixture_5_hvac_bas_not_discarded`), so a reviewer immediately sees
whether the change was intended. Drift is never silent.

The recommended discipline when a fixture goes red:

1. Decide whether the new behavior is correct. If the old lane was right, the
   change is a regression — revert or fix the formula.
2. If the new behavior is genuinely the desired policy, update the fixture
   assertion **and** bump `FORMULA_VERSION` (§6.4) in the same commit, so the
   change is recorded and replayable.

Never edit a fixture assertion to make a red test green without step 1.

### 6.3 Detection-layer partners
Several decision fixtures have a detection-layer twin (fixture 5 ↔
`test_facility_adjacency_without_cyber_phrase`; fixture 11 ↔
`test_false_positive_cui_low_relevance`). When a lane flips, checking whether the
detection twin also moved isolates the change to the detector versus the
decision formula.

### 6.4 Versioning stamps enable replay
Every decision output carries two version stamps:

- **`formula_version`** — `FORMULA_VERSION = "1.0.0"`, defined in
  `packages/intelligence/src/mactech_intelligence/decision/schemas.py` and
  stamped onto every result in `decision/engine.py`.
- **`knowledge_pack_version`** — the per-family pack stamp
  (`cyber_services=…`, `frcs_ot=…`) carried on both the pack and every detection
  report.

Together these let any historical decision be replayed against the exact formula
and pack that produced it, and let a lane distribution be attributed to a
specific formula/pack pair. Bump `FORMULA_VERSION` on any intentional change to
the scoring math or lane thresholds.

---

## 7. Shadow-run process for prompt / formula changes

Fixture tests catch changes to the **12 canonical scenarios**. They cannot tell
you how a formula change moves the lane distribution across the **live pipeline**
of real opportunities. For that, use a shadow run before shipping any prompt or
formula change.

**Process:**

1. **Freeze a window.** Pick a representative window of ingested opportunities
   (for example, the last 30 days of scored records).
2. **Run old and new in parallel.** With the current formula/pack (`old`) and
   the candidate (`new`), score every opportunity in the window. Because the
   engine is a pure function of `DecisionInputs`, both runs consume the same
   hydrated inputs — the only variable is the formula/pack.
3. **Diff the lane distribution.** Compare the counts per lane and, more
   importantly, the **per-opportunity lane transitions**: which records moved
   from `PRIME_NOW` to `PRIME_WITH_PARTNER`, which moved into or out of
   `NO_BID`, etc.
4. **Review the deltas before shipping.** Small, explainable shifts that match
   the intent of the change are expected. Large or surprising swings —
   especially anything newly landing in `NO_BID` — are a stop sign. Investigate
   the specific records before merging.
5. **Attribute with version stamps.** Tag each shadow run with its
   `formula_version` and `knowledge_pack_version` (§6.4) so the distributions are
   reproducible and the eventual production cutover is auditable.

Ship the change only when the fixture suite is green (no unintended golden
drift) **and** the shadow-run distribution delta is understood and acceptable.

---

## 8. Planned coverage (next steps)

In priority order:

1. **Decision COMPUTE worker live-DB test.** Cover
   `apps/workers/src/mactech_workers/tasks/decision.py` end to end: seed an
   opportunity + documents, run the worker against a live Postgres, and assert
   the persisted `LaneDecision` matches what the pure engine returns for the
   hydrated `DecisionInputs`. This closes the one integration seam between the
   fully tested core and the database.
2. **API-route tests.** Assert the HTTP surface that serves lane decisions
   returns the serialized `LaneDecision` contract (partner to
   `test_lane_decision_serializes`) with tenant isolation enforced.
3. **Frontend tests.** Component/integration coverage of the pursuit dashboard
   surfaces that render lanes, gates, and evidence completeness.
4. **Shadow-run harness as a script.** Promote the §7 process from a manual
   procedure to a repeatable CLI that takes a window and two formula/pack
   versions and emits the transition diff.

---

## 9. Known pre-existing failing test (record, do not fix here)

**`packages/intelligence/tests/test_cyber_scope_sam_search.py::test_keyword_match`**
fails on clean `HEAD`, independent of this overhaul.

The test asserts:

```python
assert record_matches_keywords(
    title="HVAC Controls Upgrade",
    solicitation_number="W912HQ-26-R-0001",
    keywords=("BACnet", "UMCS"),
)
```

The title/solicitation blob contains neither `BACnet` nor `UMCS`, so
`record_matches_keywords` correctly returns falsy — the **test expectation is
wrong**, not the code under test. The second half of the same test (the negative
case) is correct.

**Recommendation:** a one-line fix later — either change the expected keywords to
ones actually present (e.g. `("HVAC", "Controls")`) or change the title to
contain a supplied keyword. **Out of scope for this overhaul**; recorded here so
it is not mistaken for a regression introduced by Slices 1–4.

---

## 10. How to run

```bash
# Intelligence suites (knowledge pack, detection, decision engine)
pytest packages/intelligence/tests -q

# Worker document toolkit
pytest apps/workers/tests/test_documents_toolkit.py -q

# The full golden-fixture set alone
pytest packages/intelligence/tests/test_decision_engine.py -q
```

A green run of `test_decision_engine.py` and `test_dictionary_adapter_parity.py`
together is the minimum bar for any change touching the knowledge pack or the
scoring formula: the first proves no golden lane drifted, the second proves the
legacy dictionary is still reproduced exactly. Expect the one known-red test in
§9 until it is fixed separately.
