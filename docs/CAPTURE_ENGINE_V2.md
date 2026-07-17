# Capture Engine v2 — The Actionable Capture Engine

**Status:** Design (overhaul in progress)
**Audience:** The four founders. Half of this is plain English; the parts that touch code cite real file paths so Patrick and James can trace them.
**Related docs (written concurrently, read alongside this one):**

- `docs/CAPTURE_RULEBOOK.md` — the exact rules: signal weights, gate logic, lane definitions, decision-vector formulas.
- `docs/CAPTURE_DATA_CONTRACTS.md` — table schemas, JSONB shapes, Pydantic models, evidence-ID contract.
- `docs/CAPTURE_TEST_PLAN.md` — golden fixtures, coverage targets, how each slice is verified.

This document is the top-level "why and how." It assesses what CaptureOS does today, proposes the decision layer we are adding on top of it, describes the data flow end to end, states honestly what our data sources can and cannot do, and lays out the phased Slice plan.

---

## 1. Why this overhaul

CaptureOS today surfaces **scored notices**, not **decisions**.

For every SAM.gov notice we ingest, we compute a base 0–100 relevance score
(`packages/intelligence/src/mactech_intelligence/scoring.py`) plus two parallel
specialty scores: a "high-moat" score
(`packages/intelligence/src/mactech_intelligence/scoring_high_moat.py`) and the
FRCS/OT cyber-scope detector
(`packages/intelligence/src/mactech_intelligence/cyber_scope/`). A founder opens
the list, sees numbers, and still has to do all the thinking: is there actual
MacTech work in this notice, are we eligible to chase it, do we go prime or sub,
who do we call, and what is the next step with a date on it.

That thinking is the product. A score is an input to a decision, not the
decision. The overhaul makes the engine answer, per notice, the questions a
capture lead actually asks:

1. **Is there real MacTech work here?** — not just keyword hits, but a defensible
   scope of work we can staff and deliver.
2. **Can we pursue it?** — set-aside, NAICS, size, clearances, bonding, deadline.
   Hard eligibility, decided deterministically.
3. **Prime or sub?** — do we hold the whole thing, or is our piece a bounded work
   package under someone else's prime.
4. **Who do we contact?** — the contracting officer, or the likely primes if this
   is a subcontract play.
5. **What happens next, and by when?** — a dated action, not a vibe.

### The two pipelines we serve

The engine has to be good at two structurally different kinds of pursuit:

- **Pipeline A — MacTech as prime.** Small, direct cyber / CMMC / RMF / assessment
  / training work, roughly **$25k–$2M**, where MacTech holds the contract. These
  are notices where our NAICS and set-aside profile line up and the whole scope is
  something four senior practitioners can deliver.

- **Pipeline B — MacTech as specialty FRCS/OT cyber subcontractor.** A **bounded
  Division-25 cyber work package** (facility-related control systems, operational
  technology, RMF for building systems) buried inside a large design-build or
  construction/electrical procurement run by a construction or electrical prime.
  Here MacTech never wins the notice outright — the win is being the cyber sub the
  prime needs, on a job that is 95% not our work. The cyber-scope module already
  targets exactly this pipeline; the overhaul generalizes and operationalizes it.

These two pipelines want different signals, different eligibility logic, and
different actions. The current single-score view flattens them. Capture Engine v2
keeps them as distinct **pursuit lanes** on top of shared evidence.

---

## 2. Current-state assessment

**This overhaul is consolidation, not greenfield.** A large amount of the target
engine already exists — much of it as the `cyber_scope/` prototype. The job is to
generalize the good parts, add a decision layer on top, and stop leaving the
"what do we do about it" step to the human. This section is an honest inventory of
what is already in the repo.

### 2.1 The cyber-scope module — a working prototype of the target engine

`packages/intelligence/src/mactech_intelligence/cyber_scope/` is the closest thing
we have to Capture Engine v2 today, scoped to Pipeline B. It already does most of
what we want the generalized engine to do:

| Capability | Where |
|---|---|
| Deterministic term detection producing evidence-bearing results | `cyber_scope/matcher.py`, `cyber_scope/schemas.py` |
| `DetectionResult` carrying `term`, `normalized_term`, `category`, `weight`, `match_type`, `page_number`, `section_heading`, `document_name` | `cyber_scope/schemas.py` |
| UFGS tiering (which spec sections signal real cyber scope) | `cyber_scope/ufgs_tiers.py` + `data/cyber_scope_ufgs_tiers.yml` |
| Hidden-scope detection (cyber work not flagged in the title/NAICS) | `cyber_scope/hidden_scope.py` |
| A `PursuitModel` recommendation (prime/sub/etc.) | `cyber_scope/scorer.py`, `cyber_scope/schemas.py` |
| Suggested actions | `cyber_scope/actions.py` |
| `scan_pass` distinction: `description_only` vs `with_attachments` | `cyber_scope/analyze.py`, `cyber_scope/sources.py` |
| Persistence to the `cyber_scope_analyses` table | `cyber_scope/db_adapter.py` |
| Downstream/export shaping for LLM and reports | `cyber_scope/downstream.py`, `cyber_scope/llm_exports.py`, `cyber_scope/export_formats.py` |

The orchestration lives in the workers as
`apps/workers/src/mactech_workers/tasks/cyber_scope_scan.py`,
`.../cyber_scope_sam_search.py`, and `.../cyber_scope_summarize.py`.

**The key point:** the `DetectionResult` shape — a matched signal tied to a page, a
section heading, and a source document — is exactly the **evidence primitive** the
whole engine should be built on. v2 generalizes it beyond cyber to every signal
family.

### 2.2 Knowledge is already externalized to YAML

The cyber-scope detector does not hardcode its vocabulary. The dictionary of terms,
categories, and weights lives in `data/cyber_scope_dictionary.yml`, loaded through
`cyber_scope/dictionary.py` with an `@lru_cache`. UFGS tiers live in
`data/cyber_scope_ufgs_tiers.yml`. This is the pattern v2 extends: **knowledge in
versioned config, matching logic in code.**

### 2.3 Scoring — three parallel scores today

- **Base score** — an 8-component relevance score in
  `packages/intelligence/src/mactech_intelligence/scoring.py`.
- **High-moat score** — `scoring_high_moat.py`, boosting the specialty work MacTech
  differentiates on.
- **Cyber-scope score** — the `cyber_scope/scorer.py` output.

These are orchestrated per notice by
`apps/workers/src/mactech_workers/tasks/score.py`, which writes denormalized
headline fields onto the `opportunity_scores` table so the list view can sort and
filter without recomputing.

### 2.4 Retrieval — how notices arrive

- **Per-NAICS incremental SAM ingest** — `tasks/sam_ingest.py` pulls opportunities
  by NAICS on a schedule, incrementally.
- **Keyword saved-searches** — founder-defined title/keyword searches.
- **A title-query precedent for broad recall** — `cyber_scope/sam_search.py`
  defines `SAM_QUERY_GROUPS`, a set of title queries that cast a wider net than
  NAICS alone. This is the seed of the "5 query families" idea in v2.

### 2.5 Documents — the current limitation

`tasks/attachment_fetcher.py` fetches attachments, but it is deliberately narrow:

- **PDF only.** No DOCX, XLSX, CSV, TXT, HTML, or ZIP.
- **Title-gated.** It only downloads attachments whose titles look relevant, to
  save cost — which means it can miss the spec section that actually carries the
  scope.
- **OCR fallback** for scanned PDFs.
- **Stored as ONE concatenated `attachment_text` blob** on the `opportunities_raw`
  table. There are **no per-document rows, no provenance, no object storage, and no
  non-PDF handling.**

This is the single biggest structural gap. Detection quality is capped by document
quality, and right now we throw away which document and which page a signal came
from the moment we concatenate. Slice 2 fixes this.

### 2.6 Enrichment — already substantial

- **Incumbent detection** via USASpending — `tasks/enrich.py` writes
  `opportunities_enriched` and `awards_history`.
- **Debarment screening** via SAM Exclusions — `exclusions_cache` table.
- **Corporate-distress signals** via SEC EDGAR — `tasks/edgar_signals.py` →
  `incumbent_signals` table.

### 2.7 Amendments and solicitation extraction

- **Amendments** are tracked in the `opportunity_amendments` table (migration
  `0024`).
- **Section L / M extraction** (proposal instructions and evaluation criteria) runs
  through `extract_solicitation.py` and lands in `solicitation_extractions` plus
  matrix item tables.

### 2.8 Tenanting — application-layer only, no RLS yet

Isolation today is enforced by a `tenant_id` filter in the query layer, **not** by
PostgreSQL row-level security. RLS is deferred to Phase 4 (see
`docs/ARCHITECTURE.md` §2.2 for the eventual design). Shared notice-level tables
(the raw SAM data, which is identical across tenants) use an `unscoped_session`;
domain tables that hold per-tenant judgment carry `tenant_id`. **Every new
tenant-scoped query in v2 must filter on `tenant_id` — the filter is the only
guard we have.**

### 2.9 LLM plumbing

`AnthropicLLMClient` (`packages/intelligence/src/mactech_intelligence/llm/client.py`)
calls the Messages API, prompts for JSON, and validates the response with
`pydantic` `model_validate`. v2 keeps this pattern and tightens it: every persisted
LLM output must conform to a schema, and every claim must cite evidence IDs.

### 2.10 Known latent bug (fix scheduled)

`tasks/score.py::_make_facts` hardcodes `incumbent_excluded=None`. As a result the
debarment boost in the scorer **never fires**, even though `exclusions_cache` is
populated by the enrichment path. This is a real, silent scoring gap. It is
scheduled for **Slice 4**, where the decision engine consumes exclusions properly.

---

## 3. Proposed architecture — the decision layer

### 3.1 The core principle

The existing tables are **evidence** (detections, extractions, enrichment) and
**legacy scoring**. Capture Engine v2 is a **decision layer** that sits on top of
them: it reads the evidence, applies deterministic rules and bounded LLM judgment,
and writes **authoritative, versioned, per-lane output**.

The rules of engagement for the new layer:

- **Reuse the JSONB evidence blobs.** The detections, extractions, and enrichment
  we already compute are the raw material. We do not recompute them in the decision
  layer.
- **Add narrow tables for new decision primitives** — gates, decision vectors, work
  packages, recommendations, actions.
- **Never duplicate** `cyber_scope_analyses`, `opportunity_scores`,
  `solicitation_extractions`, or `opportunities_enriched`. The decision layer
  references them; it does not copy them.

### 3.2 The pipeline, end to end

```
                         SAM.gov (5 query families, recall-first)
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Document acquisition        │   opportunity_documents
                         │  + provenance                │   document_sections
                         │  (per-doc rows, sections,    │   (object storage,
                         │   hashes, multi-format)      │    content hashes)
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Multi-family deterministic  │   evidence rows carry
                         │  detection                   │   page + section + doc
                         │  (cyber, CMMC, RMF, training,│   (generalized from
                         │   construction/Div-25, ...)  │    cyber_scope/matcher)
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Retrieval                   │   assemble the evidence
                         │  (gather evidence + context  │   set for adjudication,
                         │   for this notice)           │   each item an evidence ID
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  LLM adjudication            │   claims MUST cite
                         │  (scope interpretation,      │   evidence IDs; output
                         │   work-package decomposition,│   validated against a
                         │   role, strategy, outreach)  │   Pydantic schema
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Deterministic HARD GATES    │   opportunity_gates
                         │  (eligibility; OVERRIDE the  │   a failed gate overrides
                         │   LLM — no gate, no bid)     │   any optimistic LLM read
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Decision vector             │   opportunity_decision_
                         │  (9 dimensions, lane-specific│   vectors
                         │   formulas)                  │
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  7 pursuit lanes             │   pursuit_recommendations
                         │  → recommendation            │   pursuit_actions
                         │  → dated actions             │   opportunity_work_packages
                         └─────────────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │  Prime-target intel          │   prime_targets
                         │  (who to sub to, for         │   opportunity_prime_targets
                         │   Pipeline B)                │
                         └─────────────────────────────┘
```

Read it top to bottom: cast a wide net at SAM, pull and parse the **whole**
procurement package with full provenance, run deterministic detection across every
signal family, gather that evidence, let the LLM interpret the ambiguous parts
(always citing evidence), then let deterministic gates and formulas produce the
authoritative decision, lane, recommendation, and dated actions.

### 3.3 New tables

**Shared (notice-level, identical across tenants — `unscoped_session`):**

| Table | Purpose |
|---|---|
| `opportunity_documents` | One row per downloaded document, with source, format, hash, and object-storage location. |
| `document_sections` | Parsed sections within a document (heading + page range) — the provenance anchor for evidence. |
| `prime_targets` | Companies that could be the prime on a subcontract play (built from USASpending award history). |

**Tenant-scoped (per-tenant judgment — carry `tenant_id`, always filtered):**

| Table | Purpose |
|---|---|
| `opportunity_decision_vectors` | The 9-dimension decision vector per notice, per tenant, versioned. |
| `opportunity_gates` | Hard eligibility gate results; a failed gate overrides the score. |
| `opportunity_work_packages` | Decomposed scope — the specific piece(s) MacTech would deliver. |
| `pursuit_recommendations` | The authoritative per-notice recommendation, including the pursuit lane. |
| `pursuit_actions` | Dated next actions attached to a recommendation. |
| `opportunity_prime_targets` | The tenant-scoped join of a notice to candidate primes, with fit/ranking. |

**Mirror columns for list-view performance:**

`opportunity_scores` gains two denormalized columns — `overall_priority` and
`pursuit_lane` — so the pipeline list can sort and filter by decision output
without joining the decision tables on every render. These mirror the authoritative
values in `pursuit_recommendations`.

### 3.4 The deterministic-vs-LLM split

This split is a hard architectural boundary, not a preference. Anything that must
be reproducible, auditable, or exact is deterministic. The LLM only touches
judgment that genuinely requires reading comprehension.

| Deterministic (code, reproducible) | LLM (bounded judgment) |
|---|---|
| Ingestion, normalization, dedup | Ambiguous scope interpretation |
| File handling, format conversion | Work-package decomposition |
| Exact signal matching | Prime-vs-sub role call |
| Hard gates (eligibility) | Customer-need summary |
| Deadline calculation | Nonstandard requirement extraction |
| Eligibility logic | Pursuit strategy |
| Score arithmetic | Competitive-position read |
| Provenance, idempotency | Outreach drafting |

**The evidence-ID contract (enforced, not aspirational):**

- Every persisted LLM output conforms to a Pydantic schema.
- Every claim the LLM makes must cite one or more **evidence IDs** — references to
  the detection or section rows we handed it.
- **Unknown or fabricated evidence IDs are rejected.** An LLM claim that cannot be
  traced back to a real piece of evidence does not get persisted. This is how we
  keep the model from confidently inventing scope. Full contract in
  `docs/CAPTURE_DATA_CONTRACTS.md`.

---

## 4. The seven pursuit lanes

Full definitions, thresholds, and reason codes live in
`docs/CAPTURE_RULEBOOK.md`. In brief, every notice resolves to exactly one lane:

| Lane | Meaning |
|---|---|
| `PRIME_NOW` | MacTech can prime this directly; pursue as prime. |
| `PRIME_WITH_PARTNER` | MacTech can prime but needs a teaming partner for part of the scope. |
| `SUB_TO_IDENTIFIED_PRIME` | Subcontract play; the likely prime(s) are known — go to outreach. |
| `SUB_TO_PRIME_NOT_YET_IDENTIFIED` | Subcontract play; primes not yet identified — find them first. |
| `SHAPE_EARLY` | Too early to bid; influence the requirement (sources sought, RFI, industry day). |
| `WATCH` | Real potential but not actionable yet; monitor for amendments/changes. |
| `NO_BID` | Do not pursue. Always carries a **reason code** (ineligible, out of scope, deadline, etc.). |

### Additive reconciliation with the legacy model

The cyber-scope module already produces a `PursuitModel` enum. We do **not** rip it
out. The reconciliation is **additive**:

- The legacy `pursuit_model` field stays populated exactly as it is today. Nothing
  that reads it breaks.
- The new `PursuitLane` is **authoritative** and is **derived deterministically**
  from four inputs: the legacy `pursuit_model`, the hard gates, the decision vector,
  and whether prime targets are present.
- The UI migrates gradually from showing the legacy model to showing the lane. Both
  exist during the transition.

---

## 5. Source limitations (be candid)

The engine's design is shaped by what our sources actually deliver. Pretending
otherwise produces wrong decisions.

- **SAM.gov gives us no reliable full-text attachment search via query
  parameters.** You cannot ask SAM "which notices mention facility control-system
  cybersecurity in an attachment." So the API is used only to build a **broad
  candidate universe** (the 5 query families), and **precision comes from
  downloading and parsing the full procurement package locally.** This is why
  document acquisition (Slice 2) is foundational — without the whole package, the
  detector is blind to the scope that lives in a spec section on page 140 of an
  attachment.

- **SAM's public feed generally exposes only the latest active version of a
  notice.** When a notice is amended, the prior version is not reliably available
  from the feed. Therefore **amendment and change detection must be done by
  CaptureOS across ingestion runs** — we preserve prior metadata and document
  content hashes, and diff each new pull against what we already hold. If we do not
  capture it on the way past, it is gone.

- **USASpending / FPDS incumbency is inference, not ground truth.** An award history
  suggests who holds the current work, but the mapping from a historical award to
  "the incumbent on this notice" is probabilistic. Every incumbent claim carries a
  **confidence level** — `confirmed`, `probable`, `possible`, or `unknown`. We
  **never label a company an incumbent without evidence**, and the confidence level
  travels with the claim into the UI and any outreach.

- **No RLS yet.** As noted in §2.8, the `tenant_id` filter is the only isolation
  guard until Phase 4. Every new tenant-scoped query in the decision layer must
  filter on `tenant_id`. A missing filter is a tenant-bleed bug, not a style nit.

---

## 6. Phased implementation — the Slices

The overhaul ships in seven slices. Slices 1–4 are built in this pass and stand up
the full decision layer end to end for the founders. Slices 5–7 are follow-on and
add depth (LLM decomposition, workflow queues, prime intel).

**Every slice ships migrations + tests + docs, runs locally, preserves tenant
isolation (`tenant_id` filter on every scoped query), and updates
`docs/PROGRESS.md`.**

### Built in this pass

**Slice 1 — Knowledge pack + query families.**
Externalize the detection knowledge into a versioned pack under
`config/capture_knowledge/*.yml` (generalizing `data/cyber_scope_dictionary.yml`
and `data/cyber_scope_ufgs_tiers.yml`). Define the **5 SAM query families** (broad,
recall-first) generalizing the `SAM_QUERY_GROUPS` precedent in
`cyber_scope/sam_search.py`. Add retrieval metrics so we can see recall per family.
Lead with **Pipeline B** — the construction/teaming query families first, since
that is where the cyber-scope prototype is already proven.

**Slice 2 — Documents and provenance.**
Introduce `opportunity_documents` and `document_sections`. Move document bytes to
object storage. Reprocess on content-hash change. Handle **multi-format**
attachments (PDF, DOCX, XLSX, CSV, TXT, HTML, ZIP) with **safe archive** handling.
Classify documents (solicitation, SOW, spec, attachment, amendment). Compute a
**package-completeness status** so we know when we are reasoning off a partial
package. This replaces the single concatenated `attachment_text` blob (§2.5).

**Slice 3 — Multi-family deterministic detection.**
Generalize the `cyber_scope/matcher.py` detector to run **every signal family** in
the knowledge pack, not just cyber. Normalize UFGS and DFARS identifiers to a
canonical form. Add **disqualifiers** — signals that argue *against* a pursuit.
Every detection remains evidence-bearing: term, normalized term, category, weight,
match type, page, section, document.

**Slice 4 — The decision engine.**
The payoff slice. Introduce `opportunity_gates` (hard gates that **override** the
score), `opportunity_decision_vectors` (the **9 dimensions**, with lane-specific
formulas), and map the **7 lanes** additively over the legacy `PursuitModel`. **Fix
the `incumbent_excluded` bug** (§2.10) so the debarment boost fires. Ship **12
golden fixtures** (see `docs/CAPTURE_TEST_PLAN.md`) and a **minimal Decision/Gates
UI panel** so founders see the decision, not just the score.

### Follow-on

**Slice 5 — Work-package decomposition + LLM adjudication.**
Wire the retrieval → LLM adjudication step with **evidence-ID validation**.
Populate `opportunity_work_packages` with the specific decomposed scope MacTech
would deliver. This is where the LLM's judgment enters the persisted decision,
under the evidence-ID contract (§3.4).

**Slice 6 — Recommendations, actions, and workflow.**
Populate `pursuit_recommendations` and **dated** `pursuit_actions`. Build the
dashboard **Prime / Sub / Shape / Review queues**. Ship the full opportunity-detail
panels. Componentize the duplicated inline opportunity card in the web app.

**Slice 7 — Prime-target intelligence.**
Build `prime_targets` and `opportunity_prime_targets` from USASpending award
history — the "who do we sub to" answer for Pipeline B. Group **related notices**
into families. Turn amendment detection (§5) into **amendment-impact actions** that
land in the queue.

---

## 7. What "done" looks like for the founders

When Slices 1–4 are in, a founder opens a notice and sees, instead of three
numbers:

- **A lane** — PRIME_NOW, SUB_TO_IDENTIFIED_PRIME, NO_BID (with a reason), and so on.
- **The gates** — which eligibility checks passed or failed, in plain language.
- **The decision vector** — why the engine scored it the way it did, per dimension.
- **The evidence** — the exact spec section and page that carries the scope, traceable.

Slices 5–7 then fill in the decomposed work package, the dated next action, the
queue it belongs in, and the prime to call. At every step the reasoning is
traceable back to a real document, a real section, and a real page — because the
engine is built on evidence, and every LLM claim has to point at it.
