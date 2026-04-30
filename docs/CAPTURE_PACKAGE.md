# Capture Package — the CaptureOS → ProposalOS handoff

**Status:** v1.0.0, schema published, endpoint live
**Integration Contract #1** in the five-app ecosystem (see `00_Ecosystem_Overview.md`)
**Owner:** CaptureOS

---

## What this is

The **Capture Package** is the single, versioned artifact CaptureOS produces when a pursuit is ready to leave capture work and enter proposal authoring. It contains everything a downstream proposal team — human or another app like the future ProposalOS — needs to start writing without re-asking CaptureOS for context.

Think of it as the "kickoff brief, machine-readable."

The package is the architectural seam between **capture** (find/qualify/decide/plan) and **proposal production** (write/review/submit). Defining it now, before ProposalOS exists, locks the contract — both apps will evolve against the same schema instead of drifting.

## Endpoint

```
GET /pursuits/{pursuit_id}/capture-package
```

Returns a fresh snapshot of the pursuit's Capture Package. No caching — call again to get a newer snapshot. Auth: standard CaptureOS Clerk JWT, tenant-scoped.

Response body: `CapturePackage` JSON, schema-versioned.

## Schema

Defined in [`packages/intelligence/src/mactech_intelligence/schemas/capture_package.py`](../packages/intelligence/src/mactech_intelligence/schemas/capture_package.py).

Top-level fields:

| Field | Purpose |
|---|---|
| `schema_version` | Semver string. Currently `"1.0.0"`. Consumers should refuse to deserialize unknown major versions. |
| `generated_at` | ISO 8601 UTC timestamp of when the snapshot was built. |
| `tenant_id`, `tenant_slug`, `pursuit_id` | Traceability across systems. |
| `opportunity` | Core opportunity metadata (notice ID, agency, NAICS, set-aside, deadline, etc.). |
| `solicitation` | Files, amendments, raw description excerpt. |
| `compliance_matrix` | Section L "shall" items with citations. |
| `requirements_matrix` | SOW/PWS/CDRL obligations with citations. |
| `evaluation` | Section M pass/fail items + scored factors. |
| `cyber` | FAR/DFARS clauses identified, CMMC level required, **posture snapshot from Codex**. |
| `capture_strategy` | Agency brief, scope, incumbent, customer priorities, must-haves, nice-to-haves. |
| `win_strategy` | Win themes + discriminators (high-level — full ghost copy is a ProposalOS concern). |
| `past_performance` | Selected library refs + library size. |
| `key_personnel` | Selected library refs + library size. |
| `teaming_partners` | Selected library refs + GovernanceOS doc state per partner. |
| `bid_decision` | Memo: decision, decider, score, rationale. |
| `governance_readiness` | Snapshot from GovernanceOS at decision time. |
| `qa_history` | Q&A entries (questions submitted, government answers). |
| `completeness` | Self-reported summary of what's filled vs. what's empty/stubbed. |

## Honesty by design — `completeness`

Many sections are **sparse in V1** because the underlying data isn't yet captured by CaptureOS (full solicitation file ingest, structured compliance matrix, GovernanceOS doesn't exist yet). Rather than hide those gaps, every package includes a `completeness` block:

```json
{
  "overall_pct": 47.5,
  "sections_complete": ["opportunity", "capture_strategy", "bid_decision"],
  "sections_partial": ["solicitation", "cyber", "qa_history"],
  "sections_missing": ["compliance_matrix", "requirements_matrix", "evaluation", "win_strategy", "governance_readiness"],
  "gaps": [
    "Solicitation: only the primary description is available. File-level ingest (Section C of requirements doc) is not yet built.",
    "Compliance matrix not generated yet (Section C — pending).",
    "GovernanceOS readiness facts feed not wired up yet (Integration Contract #2)."
  ]
}
```

Consumers can branch on `completeness` — for example, ProposalOS can refuse to start a proposal effort until `overall_pct` exceeds a threshold, or surface specific gaps as pre-kickoff to-dos.

## Versioning rules

Treat the schema as a **public API**:

- **Patch bumps** (1.0.0 → 1.0.1): docstring/description changes, no field changes.
- **Minor bumps** (1.0.0 → 1.1.0): new optional fields. Old consumers continue to work.
- **Major bumps** (1.0.0 → 2.0.0): field removals, type changes, semantic changes. Old consumers must update.

`extra="forbid"` is set on every model so unknown fields surface immediately during development rather than silently propagating bad data.

## What's in V1, and what's not

### V1 (live now)

- Opportunity metadata pulled from `OpportunityRaw`.
- Solicitation primary description URL + text excerpt (no separate file enumeration yet).
- Capture strategy assembled from `OpportunityBrief` + `OpportunityEnriched` (incumbent, scope, must-haves, nice-to-haves, red flags, suggested team roles).
- Cyber clauses extracted via regex pass over the description + brief; CMMC level detected if mentioned; posture snapshot pulled from **Codex** when `clerk_org_id` is set.
- Bid decision derived from `Pursuit.stage` + score.
- Q&A history from `OpportunityQuestion`.
- Library sizes for past performance, key personnel (founders), teaming partners. `selected[]` empty until per-pursuit linking lands.
- `completeness` summary + gap list.

### Deferred (sections present in schema, empty until built)

- **Compliance matrix** — Section L extraction. Requires the solicitation decoder (Section C of `CaptureOS_Requirements.md`).
- **Requirements matrix** — SOW/PWS extraction. Same dependency.
- **Evaluation** — Section M pass/fail + scored factors.
- **Win strategy** — themes + discriminators captured per-pursuit. Currently no UI for this.
- **Governance readiness** — depends on GovernanceOS (Integration Contract #2).
- **Teaming partner doc state** — depends on GovernanceOS.
- **Selected library refs** — depends on per-pursuit linking of past-performance/key-personnel/teaming-partner records (not yet built).

The point is: ProposalOS clients can write code against the full schema *today* and the empty fields populate as CaptureOS matures. No client refactor required.

## Build path inside CaptureOS

```
apps/api/src/mactech_api/routes/capture_package.py
        └── calls
            packages/intelligence/src/mactech_intelligence/capture_package_builder.py
                        └── reads from packages/db/src/mactech_db/models/*
                        └── pulls cyber posture from packages/integrations/src/mactech_integrations/codex
```

The builder is stateless, takes an `AsyncSession` and an optional `CodexClient`, and is safe to call repeatedly.

## Failure modes

| Condition | Behavior |
|---|---|
| Pursuit not found in tenant | HTTP 404 |
| Pursuit references a missing opportunity | HTTP 500 + log (data inconsistency) |
| Codex unavailable / errors | Cyber posture snapshot = `null`, `sufficiency = "unknown"`. Package builds successfully. |
| No `clerk_org_id` on tenant | Same as Codex unavailable. |
| Description text empty | Cyber clause detection returns `[]`, package still builds. |

## How ProposalOS will use this

When ProposalOS comes online, the integration will be:

1. Capture lead clicks "Hand off to proposal team" in CaptureOS.
2. CaptureOS calls `GET /pursuits/{id}/capture-package` and posts the JSON to ProposalOS's import endpoint.
3. ProposalOS validates the schema version, checks `completeness.overall_pct`, surfaces any gaps to the proposal manager as pre-kickoff blockers.
4. Once cleared, ProposalOS opens the writing workspace with the compliance matrix as the spine.

Until then, you can hit the endpoint manually from any CaptureOS-authenticated client to inspect what the handoff would look like. It's also the best feedback signal for which V1 gaps to close next — every red item in `completeness.gaps` is a future sprint candidate.

## Related

- [`docs/00_Ecosystem_Overview.md`](00_Ecosystem_Overview.md) — the five-app picture
- [`docs/CaptureOS_Requirements.md`](CaptureOS_Requirements.md) — Section H defines this artifact
- [`docs/ProposalOS_Requirements.md`](ProposalOS_Requirements.md) — Section A is the consumer side
