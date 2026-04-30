# MacTech Federal Contracting Platform — Ecosystem Overview

**Version:** 0.1 (draft)
**Audience:** MacTech founders, future engineers, future product partners
**Purpose:** Frame the five apps that together cover the full federal contracting lifecycle, and define how they connect.

Read this before any of the per-app requirements documents. The per-app docs (`CaptureOS_Requirements.md`, `ProposalOS_Requirements.md`, `GovernanceOS_Requirements.md`) all assume you've internalized this overview.

---

## The five apps

MacTech's federal contracting platform is split across five purpose-built apps. Each has one job. Together they cover everything from "we don't have a company yet" to "the contract is closed out and the lessons learned are filed."

| App | Job | Owner Pillar | Status |
|---|---|---|---|
| **GovernanceOS** | Make and keep the company eligible to do federal work, then run the contract after award | Brian — Quality | Proposed |
| **CaptureOS** | Find federal opportunities, qualify them, decide which to chase, hand the proposal team a complete game plan | Capture / BD | Building (Phase 1) |
| **ProposalOS** | Turn the game plan into a finished, submittable proposal | Proposal Mgmt | Future (Phase 3+) |
| **PricingOS** | Build the price volume — labor categories, indirect rates, profit, BOE math | Finance | Future |
| **Codex** | Manage cybersecurity posture — SSP, POA&M, SPRS score, CMMC status | Patrick — Cyber | Existing (sibling product) |

## The picture

```
              ┌────────────────────────────────────────┐
              │             GovernanceOS                │
              │   corporate setup • teaming docs •      │
              │   reps & certs • post-award ops •       │
              │   reporting • closeout                  │
              └─────┬──────────┬──────────┬───────┬────┘
                    │          │          │       │
        readiness   │ reps &   │ indirect │       │ award
        facts       │ certs    │ rates    │       │ intake
                    ▼          ▼          ▼       ▲
            ┌──────────┐  ┌────────────┐  ┌──────────┐
            │CaptureOS │→ │ProposalOS  │← │PricingOS │
            │find/plan │  │write/submit│  │   math   │
            └──────────┘  └────────────┘  └──────────┘
                  ▲             ▲              ▲
                  │             │              │
                  └─────────────┴──────────────┘
                                │
                          cyber posture
                                │
                            ┌───┴────┐
                            │ Codex  │
                            └────────┘
```

## The line in the sand

> **CaptureOS handles everything up to the moment someone sits down to write the proposal. The minute writing begins, you're in ProposalOS.**

GovernanceOS is the bookend on either side: corporate readiness *before* CaptureOS can clear a bid, and contract execution + reporting + closeout *after* ProposalOS submits. Codex provides cyber posture as a cross-cutting service to all three. PricingOS does the cost math during the proposal phase.

## The seven integration contracts

The ecosystem is held together by seven well-defined data feeds. Each is the responsibility of the *publisher* app to define and version. Consumer apps treat them as black boxes.

| # | Contract | Publisher | Consumer | Purpose |
|---|---|---|---|---|
| 1 | **Capture Package** | CaptureOS | ProposalOS | The handoff at "we've decided to bid." Contains opportunity metadata, every solicitation file + amendment, compliance matrix, requirements matrix, cyber clauses + posture snapshot, capture strategy, win themes, bid/no-bid memo, selected past performance + key personnel, teaming partner refs, Q&A history. |
| 2 | **Readiness Facts** | GovernanceOS | CaptureOS | "Are we ready to bid this kind of contract?" Includes: accounting system DCAA status, FCL status + level, set-aside eligibility, E-Verify status, reps & certs current, teaming docs executed per partner. CaptureOS uses this to gate bid/no-bid. |
| 3 | **Reps & Certs Feed** | GovernanceOS | ProposalOS | The current Section K profile (the 50+ legal certifications every proposal must restate). Auto-fills proposal forms. Versioned per submission. |
| 4 | **Cyber Posture** | Codex | CaptureOS, ProposalOS, GovernanceOS | SPRS score, CMMC level, NIST 800-171 controls coverage, gap report. CaptureOS uses it for eligibility + clause-fit checks; ProposalOS uses it to draft the cybersecurity volume; GovernanceOS displays it on the readiness dashboard. |
| 5 | **Indirect Rates + Rate Cards** | GovernanceOS | PricingOS | Approved fringe / OH / G&A pools, labor categories, blended/burdened rates. PricingOS does the math; the rates themselves are governed (DCAA-relevant). |
| 6 | **Price Volume** | PricingOS | ProposalOS | The finished cost/price volume artifact, formatted per solicitation rules. ProposalOS attaches it; never edits it. |
| 7 | **Award Intake** | ProposalOS | GovernanceOS | "We won" event with awarded contract details — number, KO, value, period of performance, CLINs, key clauses. Kicks off post-award contract execution governance. |

## Cross-cutting principles

These apply to every app in the ecosystem. Each per-app doc reasserts the relevant ones in its own non-functional section.

1. **CMMC 2.0 Level 2 alignment from day one.** Every architectural decision considers CUI boundaries, access control, audit logging, and data residency. CaptureOS, ProposalOS, GovernanceOS handle CUI at varying intensity; design assumes CUI everywhere.
2. **Multi-tenant with hard isolation.** Each customer's data — opportunities, pursuits, capability data, proposals, contracts, governance records — must never leak across tenants. Row-level security at the database, tenant-scoped queries enforced at the ORM layer.
3. **One source of truth per fact.** Each fact lives in exactly one app. Other apps reference it; they don't copy it. Cyber posture lives in Codex, not in CaptureOS. Reps & certs live in GovernanceOS, not in ProposalOS. The Capture Package is a *snapshot* explicitly versioned for handoff — it's the only place where one app's data is mirrored to another.
4. **Audit trail everywhere.** Every read of a solicitation, every bid decision, every certification renewal, every proposal edit, every signed teaming agreement — logged with who, when, why.
5. **US data residency.** Eventually GovCloud. Commercial cloud (US regions) is acceptable in early Phase 1.
6. **Idempotent ingestion.** Any data pull (SAM.gov, USASpending, etc.) is safely re-runnable.
7. **Rate-limit aware.** Every external API consumer respects the source's limits with exponential backoff.
8. **Veteran-owned voice.** Sober, plainspoken, competent. No marketing fluff. No emoji in product UI.

## What's explicitly out of scope for the entire ecosystem

These are *not* future MacTech products. They live in third-party tools, and our apps integrate with them:

- **Accounting / general ledger** → Deltek, Unanet, QuickBooks. GovernanceOS holds policy + readiness state and references the system; it never replaces it.
- **Timekeeping** → Deltek Time, Unanet, QuickBooks Time. Same pattern as above.
- **E-signature** → DocuSign, Adobe Sign. Used by GovernanceOS and ProposalOS via integration.
- **Auto-clicking the government submit button at PIEE / SAM / agency portals.** Always a human. ProposalOS produces the bundle and a submission checklist; the human uploads.
- **Post-award contract delivery (the actual work).** Customer's own project management tools (Jira, MS Project, etc.).

## Phasing

The ecosystem doesn't get built all at once. Recommended sequence:

| Phase | Build | Why |
|---|---|---|
| **1 (now)** | CaptureOS core (find / qualify / score / capture intel / Sources Sought / opportunity Q&A) | MacTech's own BD weapon. Already underway. |
| **2** | CaptureOS solicitation decoder (compliance matrix, requirements matrix, cyber clauses) + Capture Package export schema | Closes the seam to ProposalOS *before* ProposalOS exists. |
| **3** | GovernanceOS V1 — corporate identity vault, reps & certs, set-aside tracking, teaming doc vault, readiness dashboard | Brian's pillar. First customer-facing governance surface. Front-bookend done. |
| **4** | ProposalOS V1 — Capture Package import, volume drafting, color-team workflow, compliance audit, submission companion | Middle of the pipeline. Once CaptureOS is mature enough to produce a complete Capture Package. |
| **5** | GovernanceOS V2 — post-award (LOC/LOF, CPSR, eSRS, VETS-4212, REA, closeout, CPARS) | Back-bookend. Triggers when the first MacTech contract is won. |
| **6+** | PricingOS | Spin out only when proposal pricing is real and recurring. |

Codex evolves on its own track in parallel — it predates this ecosystem and stays independent.

---

*Cross-references: `CaptureOS_Requirements.md`, `ProposalOS_Requirements.md`, `GovernanceOS_Requirements.md`.*
