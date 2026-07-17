# CAPTURE_RULEBOOK.md — MacTech CaptureOS Capture Decision Logic

**Status:** Authoritative rulebook for the capture decision layer.
**Scope:** The rules, taxonomy, gates, lanes, reason codes, and scoring formulas that turn a raw opportunity into a bid/no-bid recommendation with a pursuit lane.
**Siblings:** `docs/CAPTURE_ENGINE_V2.md` (runtime and orchestration), `docs/CAPTURE_DATA_CONTRACTS.md` (row shapes and field types), `docs/CAPTURE_TEST_PLAN.md` (fixtures and acceptance criteria). Where those documents describe *how* a value is computed or stored, this document is the source of truth for *what the rule is*. If they disagree, the rulebook wins and the sibling gets corrected.

This is a decision system for federal capture, not a keyword scanner. Detection is table stakes. The intelligence — which signals matter, which gates are hard, which lane to run, and why — lives here and must be reproducible from stamped versions on every record.

---

## 0. Design commitments

1. **Deterministic gates override weighted scores.** A hard gate is a fact, not an opinion. The scoring model produces a number; the gates decide whether that number is allowed to recommend a pursuit. The LLM may *explain* a gate but may not *overrule* one without an explicit human-review exception.
2. **Every recommendation is reproducible.** Each decision record stamps the prompt, model, rule/formula set, and knowledge-pack versions in play. Given those four stamps and the source opportunity, the recommendation can be regenerated exactly.
3. **Evidence is retained, not discarded.** Detection keeps the page and section where each signal was found. A recommendation that cannot cite its evidence is a bug.
4. **No naked "low score."** A NO_BID must carry a real reason code. "The score was low" is never, by itself, an acceptable no-bid explanation.
5. **Replaceable without code changes.** The knowledge pack is versioned config. Analysts add concepts, aliases, weights, and gates by editing YAML and cutting a new pack version. Code changes are for engine behavior, not for vocabulary.

---

## 1. Knowledge taxonomy

The capture engine reads a **versioned knowledge pack** at `config/capture_knowledge/*.yml`. The pack is the single vocabulary and weighting source for detection, gating, and scoring. It is versioned as a unit (`knowledge_pack_version`), and a decision record is only reproducible against the pack version it was scored under.

### 1.1 The eight family files

| File | Family | Holds |
|---|---|---|
| `cyber_services.yml` | Direct cyber delivery | CMMC, DFARS 7012-series, NIST 800-171, RMF/ATO/eMASS, STIG/ACAS, ConMon, assessment/IR concepts |
| `frcs_ot.yml` | FRCS and OT cyber | UFC 4-010-06, UFGS 25 05 11 and Division 25, PIT, ICS/SCADA/PLC/DCS, control-system RMF artifacts |
| `construction_systems.yml` | Facility-system adjacency | HVAC/EMS/BAS, electrical power monitoring, ESS/CCTV/ACS, fire alarm, metering, microgrid |
| `clauses_frameworks.yml` | Clauses and frameworks | FAR/DFARS clauses, CMMC levels, NIST/CNSSI/FIPS references, safeguarding and marking rules |
| `agency_offices.yml` | Agency and office context | USACE/NAVFAC/AFCEC districts, branch-specific offices, contract locations and triggers |
| `acquisition_signals.yml` | Acquisition context | Design-build vs DBB, MILCON/SRM, MATOC/SATOC/MACC/IDIQ, task-order and teaming signals |
| `disqualifiers.yml` | Barriers and disqualifiers | Clearance, license, bonding, self-performance, OEM, geographic, and vehicle barriers with gate codes |
| `pursuit_playbooks.yml` | Pursuit playbooks | Lane heuristics, partner-target patterns, shaping actions, per-lane action templates |

### 1.2 Concept schema

Each concept in any family file carries the following keys:

| Key | Meaning |
|---|---|
| `id` | Normalized, stable identifier. Immutable once published. |
| `canonical_name` | Human-readable primary name. |
| `aliases` | Alternate spellings and long forms. |
| `abbreviations` | Short forms (e.g. `SPRS`, `POA&M`). |
| `exact_phrases` | Literal strings that count as a match. |
| `regex` | Pattern(s) for structured identifiers and spacing/punctuation variants. |
| `related_concepts` | IDs of adjacent concepts, used for co-occurrence and lane heuristics. |
| `evidence_category` | Which `DetectedCategories` field this concept feeds (see 1.4). |
| `positive_weight` | Contribution when present and relevant. |
| `negative_weight` | Contribution when the concept is evidence *against* fit. |
| `disqualifier` | Boolean. When true, the concept can trip a hard gate. |
| `gate_code` | Required when `disqualifier: true`. The gate/reason code raised (see §3, §5). |
| `source_ref` | Citation to the governing document (UFC/UFGS/DFARS/NIST/agency policy). |
| `effective_date` | When the concept becomes valid; supports point-in-time reproduction. |
| `enabled` | Boolean kill switch without deleting the concept. |

### 1.3 Identifier normalization

Detection normalizes structured identifiers so that every surface form of the same reference collapses to one canonical `id`. Two worked examples the pack must handle:

- **UFGS sections** — `25 05 11`, `25-05-11`, `250511`, `UFGS 25 05 11`, and `Section 25 05 11` all normalize to the single canonical id for that section.
- **DFARS clauses** — `252.204-7012`, `252 204 7012`, `2522047012`, and `DFARS 252.204–7012` (en dash) all normalize to the single canonical id for that clause.

Normalization strips spacing, punctuation, prefixes (`UFGS`, `Section`, `DFARS`, `NIST SP`), and dash variants (hyphen, en dash, em dash) before matching. `regex` on the concept covers the variant forms; `exact_phrases` and `aliases` cover the long forms.

### 1.4 Evidence category mapping

`evidence_category` maps each concept to an existing `cyber_scope` `DetectedCategories` field, so the new pack drives the same detection surface already in use:

| `evidence_category` | `DetectedCategories` field |
|---|---|
| UFC / FRCS | `ufc_frcs` |
| RMF / ATO / eMASS | `rmf_ato_emass` |
| NIST / CNSSI / FIPS | `nist_cnssi_fips` |
| OT / ICS / SCADA / PIT | `ot_ics_scada_pit` |
| Branch-specific | `branch_specific` |
| Contract location triggers | `contract_location_triggers` |
| FAR / DFARS / CMMC | `far_dfars_cmmc` |

### 1.5 Supersession and compatibility

The knowledge pack **supersedes** `data/cyber_scope_dictionary.yml` and `data/cyber_scope_ufgs_tiers.yml`. It does not delete them. A **compatibility adapter** reads the legacy dictionary and UFGS tier tables and projects them into pack concepts at load time, so:

- Existing detection keeps working while the pack is populated family by family.
- Legacy `term` / `normalized_term` / `weight` / `aliases` / `regex` map onto `canonical_name` / `id` / `positive_weight` / `aliases` / `regex`.
- Legacy UFGS `tier_multipliers` and `center_of_gravity_companions` are represented as concept weights and `related_concepts` in `frcs_ot.yml`.

The pack is **replaceable without code changes**: analysts edit YAML, bump `knowledge_pack_version`, and the engine reloads. No recompile, no migration, for vocabulary changes.

---

## 2. Signal families

Detection groups concepts into five signal families. Each detected signal retains its **page and section evidence** — where in the solicitation, SOW, or amendment it was found — so downstream scoring and the human reviewer can trace every claim.

### 2.1 Direct Cyber Delivery
Cyber work MacTech performs directly.

CMMC · DFARS 252.204-7012 / -7019 / -7020 / -7021 · NIST SP 800-171 · SPRS · RMF · ATO · eMASS · SSP · POA&M · STIG · ACAS · Nessus · ConMon · security controls assessment · penetration testing · vulnerability assessment · incident response · tabletop exercise · after-action report · cyber training.

### 2.2 FRCS and OT Cyber
Control-system cybersecurity — MacTech's differentiated center of gravity.

UFC 4-010-06 · UFGS 25 05 11 · Division 25 · FRCS · PIT / Platform Information Technology · OT · ICS · SCADA · PLC · DCS · UMCS · BAS · BACnet · Modbus · LonWorks · OPC · industrial Ethernet · control-system RMF · cybersecurity commissioning · control-system inventory · network diagram · security control traceability matrix · cybersecurity submittal · authorization package · continuous monitoring strategy.

### 2.3 Facility-System Adjacency
Systems that carry or generate cyber scope even when the solicitation is framed as construction or controls.

HVAC controls · energy management · utility monitoring · microgrid · generator controls · electrical power monitoring · substation automation · water/wastewater controls · pump controls · central plant controls · fire alarm · mass notification · access control · intrusion detection · electronic security · CCTV · lighting controls · metering · BMS.

### 2.4 Construction & Acquisition Context
Signals that set the contracting shape and drive prime-versus-sub reasoning.

design-build · design-bid-build · MILCON · renovation · modernization · SRM · MATOC · SATOC · MACC · IDIQ · task order · prime contractor · subcontracting plan · specialty subcontractor · commissioning agent · controls integrator · electrical contractor · systems integrator.

### 2.5 Barriers & Disqualifiers
Conditions that gate eligibility and deliverability. Members here typically carry `disqualifier: true` and a `gate_code`.

mandatory facility clearance · safeguarding level · citizenship requirement · cleared staffing count · professional engineer requirement · state electrical license · bonding · self-performance percentage · OEM / authorized-dealer requirement · geographic restriction · contract vehicle restriction · minimum revenue · minimum years in business · mandatory past performance · security clearance · response deadline · site visit · bid guarantee.

---

## 3. Deterministic gates

Gates are stored as `opportunity_gates` rows. A **hard** gate (`severity: hard`) overrides the weighted score: it can force a lane change or a NO_BID after scoring, regardless of how high the number was. A **soft** gate (`severity: soft`) reduces confidence but does not force NO_BID. The LLM may explain a gate but cannot clear one; a hard gate is cleared only by an explicit **human-review exception**, which is itself recorded.

Gates run *after* the decision vector is computed, then override it.

### 3.1 Hard gates

| Condition | Effect | Gate / reason |
|---|---|---|
| Response deadline has passed | Force NO_BID | `EXPIRED` (`NO_BID`) |
| Ineligible set-aside and no viable subcontract path | Force NO_BID | `INELIGIBLE_SET_ASIDE` (`NO_BID`) |
| Mandatory contract vehicle unavailable and no sub path | Force NO_BID | `VEHICLE_UNAVAILABLE` (`NO_BID`) |
| Bonding requirement beyond configured capacity | Suppress `PRIME_NOW` | `BONDING_GAP` (suppress prime; evaluate sub) |
| Construction self-performance dominates the scope | Suppress `PRIME_NOW`, evaluate `SUB` | self-perform gate |
| An FRCS cyber work package exists | Never discard solely because primary NAICS is construction | FRCS-carve-out (protective gate) |
| A direct small cyber scope exists and eligibility is satisfied | Evaluate `PRIME_NOW` regardless of a generic title | cyber-carve-out (protective gate) |
| Solicitation attachments incomplete | Lower confidence and create a missing-information action | missing-info (also affects `evidence_completeness_score`) |
| Incumbent excluded/debarred per `exclusions_cache` | Raise exclusion gate | `INELIGIBLE_EXCLUDED_INCUMBENT` |

Notes:

- **Protective gates** (FRCS carve-out, cyber carve-out) prevent *false negatives*. They stop the engine from throwing away an opportunity that carries real MacTech scope just because the wrapper — NAICS or title — reads as generic construction. They are hard because a weighted average would otherwise bury a small-but-real cyber package.
- **`INELIGIBLE_EXCLUDED_INCUMBENT`** is where the known `incumbent_excluded` bug fix lands. The exclusion check reads `exclusions_cache` for the incumbent entity and raises this hard gate when a match is found; prior behavior failed to propagate that state into the decision. The gate is mandatory (Exclusions screening is required per project data-source policy).
- The **attachments-incomplete** gate does not force NO_BID on its own. It lowers confidence, pins `evidence_completeness_score` to the appropriate rung (§6.2), and opens a missing-information action so a human can pull the missing files.

### 3.2 Soft gates

Soft gates (`severity: soft`) reduce confidence but never force NO_BID. Representative soft gates:

- Ambiguous or partially matched set-aside where a sub path plausibly exists.
- Geographic stretch that is workable but raises delivery cost.
- Thin or dated past performance that is a fit risk rather than a stated bar.
- Aggressive but achievable response deadline.
- Site visit or bid guarantee noted but not yet confirmed.

A soft gate lowers the relevant dimension and the overall confidence; it may nudge a lane (e.g. toward `PRIME_WITH_PARTNER`) but it does not by itself remove the opportunity from pursuit.

---

## 4. Pursuit lanes

The engine assigns exactly one of seven lanes. Lane definitions and "use when" criteria:

| Lane | Use when |
|---|---|
| `PRIME_NOW` | MacTech can prime today. Eligibility is satisfied, the scope is deliverable within self-performance and bonding limits, and there is real MacTech scope (cyber or FRCS). No hard gate suppresses prime. |
| `PRIME_WITH_PARTNER` | MacTech should prime but needs a partner to cover a capability, capacity, self-performance, or bonding gap that would otherwise suppress a solo prime. MacTech holds the prime relationship and the cyber/FRCS scope. |
| `SUB_TO_IDENTIFIED_PRIME` | The winning play is to sub, and specific prime target(s) are already identified (incumbent, likely bidder, or a known teaming partner). Pursue the teaming conversation now. |
| `SUB_TO_PRIME_NOT_YET_IDENTIFIED` | The winning play is to sub, but no prime target is identified yet. Work the market to find and qualify a prime. |
| `SHAPE_EARLY` | The opportunity is pre-solicitation or ambiguous and can be influenced. Engage the office, submit RFI/sources-sought input, shape scope and set-aside before the solicitation locks. |
| `WATCH` | Not actionable now but worth tracking — future recompete, forecast item, or an opportunity awaiting a trigger. Keep it in the pipeline; re-evaluate on change. |
| `NO_BID` | Do not pursue. Always carries a §5 reason code. Forced by any hard-gate failure; otherwise chosen when no realistic path to a worthwhile pursuit exists. |

### 4.1 Legacy PursuitModel mapping

The engine deterministically maps the legacy `cyber_scope` `PursuitModel` values to the new lanes. This mapping is applied *before* gates; a hard-gate failure then overrides it to `NO_BID`.

| Legacy `PursuitModel` | New lane |
|---|---|
| `NO_ACTION` | `NO_BID` if a hard gate is tripped, else `WATCH` |
| `WATCHLIST` | `WATCH` |
| `CLARIFICATION_REQUIRED` | `SHAPE_EARLY` |
| `PRIME_PURSUE` | `PRIME_NOW` if deliverability clears the self-perform and bonding gates, else `PRIME_WITH_PARTNER` |
| `CMMC_COMPLIANCE_SUPPORT` | `PRIME_NOW` if deliverability clears self-perform/bonding, else `PRIME_WITH_PARTNER` |
| `CYBER_SUPPORT_ONLY` | `PRIME_NOW` if deliverability clears self-perform/bonding, else `PRIME_WITH_PARTNER` |
| `SUBCONTRACTOR_PURSUE` | `SUB_TO_IDENTIFIED_PRIME` if prime target(s) exist, else `SUB_TO_PRIME_NOT_YET_IDENTIFIED` |
| `FRCS_OT_SPECIALIST` | `SUB_TO_IDENTIFIED_PRIME` if prime target(s) exist, else `SUB_TO_PRIME_NOT_YET_IDENTIFIED` |
| *(any of the above)* | **Any hard-gate failure forces `NO_BID`** |

---

## 5. NO_BID reason codes

Every `NO_BID` carries one of these reason codes. A generic "low score" is never, on its own, a valid no-bid explanation — the engine must name the specific barrier.

| Reason code | Meaning |
|---|---|
| `INELIGIBLE_SET_ASIDE` | Set-aside excludes MacTech and no viable sub path exists. |
| `VEHICLE_UNAVAILABLE` | Mandatory contract vehicle MacTech does not hold, no sub path. |
| `SCOPE_TOO_LARGE` | Scope exceeds MacTech's realistic delivery capacity even with a partner. |
| `STAFFING_UNREALISTIC` | Required staffing (count, clearances, key personnel) is not achievable in time. |
| `PAST_PERFORMANCE_GAP` | Mandatory past-performance bar MacTech cannot meet. |
| `MANDATORY_LICENSE_GAP` | Required license (e.g. state electrical, PE) MacTech lacks and cannot cover. |
| `MANDATORY_CLEARANCE_GAP` | Required facility/personnel clearance MacTech lacks and cannot cover. |
| `BONDING_GAP` | Bonding requirement beyond configured capacity, no workable path. |
| `GEOGRAPHIC_MISMATCH` | Location/geographic restriction MacTech cannot satisfy. |
| `DEADLINE_UNWORKABLE` | Response window too short to produce a credible bid. |
| `NO_REAL_MACTECH_SCOPE` | No genuine cyber or FRCS scope for MacTech to deliver. |
| `LOW_MARGIN_COMMODITY` | Commodity buy with margin too thin to justify pursuit. |
| `OEM_RESTRICTION` | OEM / authorized-dealer requirement MacTech cannot meet. |
| `DUPLICATE` | Duplicate of an already-tracked opportunity. |
| `EXPIRED` | Response deadline already passed. |
| `OTHER` | Documented reason not covered above; requires a free-text justification. |

---

## 6. Decision-vector scoring

The engine computes a **decision vector** of nine dimensions, each on a 0–100 scale. Dimensions are computed from the retained evidence and the knowledge-pack weights. `overall_priority_score` is a lane-specific weighted composite — **not** a naive average — and hard gates override it after computation.

### 6.1 Dimensions and inputs

| Dimension | Inputs |
|---|---|
| `relevance_score` | Density and strength of direct-cyber and FRCS/OT signals; alignment to MacTech NAICS and center-of-gravity concepts; co-occurrence of related concepts. |
| `prime_fit_score` | Fit of the scope to MacTech priming: eligibility, self-performance feasibility, capability coverage, contract-shape fit (IDIQ/task order/standalone). |
| `subcontract_fit_score` | Fit of the carved cyber/FRCS package to a subcontract role; presence and quality of identifiable prime targets; teaming precedent. |
| `winability_score` | Competitive posture: set-aside advantage, incumbent presence, number and strength of likely bidders, MacTech differentiation on FRCS/cyber. |
| `deliverability_score` | Ability to execute if awarded: staffing, clearances, licenses, bonding, geography, schedule feasibility. |
| `strategic_value_score` | Fit to MacTech strategy: agency relationship value, past-performance building, vehicle access, follow-on and recompete potential. |
| `urgency_score` | Time pressure: response deadline proximity, site-visit/RFI windows, shaping windows still open. |
| `evidence_completeness_score` | How much of the solicitation record is in hand (see ladder in 6.2). |
| `overall_priority_score` | Lane-specific weighted composite of the above (see 6.3). |

### 6.2 Evidence completeness ladder

`evidence_completeness_score` is set by rung, based on what portion of the record is accessible:

| Score | Record in hand |
|---|---|
| 20 | Metadata only |
| 40 | Description available |
| 60 | Some attachments available |
| 80 | Core solicitation + SOW available |
| 100 | All accessible, including amendments |

The attachments-incomplete gate (§3.1) pins this dimension to the correct rung and raises a missing-information action rather than guessing.

### 6.3 Lane-specific overall_priority formulas

`overall_priority_score` uses one of two weightings depending on whether the play is prime or sub:

**Prime priority**

```
overall_priority =
    0.25 * relevance_score
  + 0.25 * prime_fit_score
  + 0.20 * winability_score
  + 0.20 * deliverability_score
  + 0.10 * strategic_value_score
```

**Sub priority**

```
overall_priority =
    0.25 * relevance_score
  + 0.30 * subcontract_fit_score
  + 0.15 * winability_score
  + 0.15 * deliverability_score
  + 0.15 * strategic_value_score
```

`overall_priority_score` is **not** a naive average of the nine dimensions. It is the lane-appropriate weighted composite above. **Hard gates override the weighted score after it is computed** — a high `overall_priority` does not survive a tripped hard gate, and a protective gate can keep a modest score in pursuit.

---

## 7. Versioning

Every decision record stamps four versions so any recommendation is reproducible and auditable:

| Stamp | Pins |
|---|---|
| `prompt_version` | The exact prompt template used for any LLM explanation/extraction. |
| `model_version` | The model (and revision) that produced LLM outputs. |
| `rule_set` / `formula_version` | The gate logic and scoring-formula version in effect. |
| `knowledge_pack_version` | The `config/capture_knowledge/*.yml` pack version detection and weighting ran against. |

Given these four stamps plus the source opportunity, a recommendation can be regenerated exactly. Changing a weight, a gate, a prompt, or a model produces a new version stamp — never a silent in-place change — so the audit trail always explains why an older recommendation differs from a re-run.
