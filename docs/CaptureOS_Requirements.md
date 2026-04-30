# CaptureOS — Requirements Specification

**Version:** 0.1 (draft)
**Audience:** MacTech founders, future engineers, future product partners
**Read first:** `00_Ecosystem_Overview.md`

---

## Purpose

Find federal opportunities, decide which ones to chase, decode what they require, and hand the proposal team a complete game plan.

CaptureOS is the **front of the pipeline**. It pulls *cyber posture* from Codex and *company readiness facts* from GovernanceOS, then produces a single, well-defined artifact — the **Capture Package** — that ProposalOS consumes when writing begins.

CaptureOS is also the licensable SaaS surface. Other DIB contractors will pay for this. ProposalOS, GovernanceOS, and PricingOS are eventual product extensions; CaptureOS is the wedge.

## Who uses it

- **Capture lead / BD lead** — primary user; decides what to pursue
- **Pursuit owner** — drives a single opportunity from "found" to "ready to write"
- **Executive / founder** — reads dashboards, approves bid/no-bid
- **Cyber lead** — confirms cyber posture is sufficient (via Codex pull) for each pursuit
- **Compliance / contracts lead** — confirms readiness facts (via GovernanceOS pull) for each pursuit
- **External DIB customers** *(eventual, multi-tenant SaaS)*

---

## What it does (functional requirements)

### A. Opportunity discovery

A1. Pull live opportunities from SAM.gov on a schedule.
A2. Pull historical award + spending data from USASpending and FPDS-NG.
A3. Pull small-business / SDVOSB / 8(a) verifications from SBA DSBS.
A4. Pull agency forecasts (next-year planned buys) via configured scrapers.
A5. Pull broader web signals (industry news, hiring, agency announcements).
A6. Deduplicate and normalize into a single opportunity feed.
A7. Allow each tenant to define **saved searches** with filters: NAICS codes, set-asides, agencies, keywords, dollar range, place of performance.
A8. Score every opportunity for fit, freshness, and competitiveness using tenant capability profile.

### B. Eligibility check

B1. Verify the company is registered and active in SAM.gov.
B2. Verify UEI and CAGE code are current.
B3. Check the company against the federal exclusions / debarment list.
B4. Check that NAICS codes match the opportunity's required NAICS.
B5. Check set-aside eligibility (small business, SDVOSB, 8(a), HUBZone, WOSB) by **pulling current set-aside status from GovernanceOS**.
B6. Check cyber posture sufficiency by **pulling SPRS score, CMMC level, and 800-171 coverage from Codex** against the cyber clauses identified in the solicitation.
B7. Check infrastructure readiness for the contract type (CR, T&M, FFP) by **pulling accounting system status, FCL, E-Verify, and reps & certs currency from GovernanceOS**.

### C. Solicitation decoder

C1. Download every file the government posted: solicitation, attachments, amendments, exhibits, wage determinations, Q&A, drawings, DD254.
C2. Detect file type and parse text (PDF, DOCX, XLSX, ZIP, scanned PDF via OCR).
C3. Extract Section L (instructions to offerors) and Section M (evaluation factors).
C4. Build a **compliance matrix** — every "you must say X" instruction, with source citation.
C5. Build a **requirements matrix** — every "you must do X" technical, operational, security obligation.
C6. Identify pass/fail items vs. scored items.
C7. Identify required certifications, clearances, accounting systems, insurance, bonding.
C8. Identify all cybersecurity clauses (FAR 52.204-21, DFARS 7012/7019/7020/7021, NIST 800-171, CMMC level required).
C9. Identify subcontractor flow-down obligations.
C10. Detect whether the work involves CUI, FCI, ITAR, classified, or export-controlled data.

### D. Bid/no-bid workflow

D1. Score each opportunity against tenant's capability profile.
D2. Auto-route to the right founder/owner based on NAICS or set-aside.
D3. Capture a structured bid/no-bid memo (rationale, score, decision, decider, date).
D4. **Block bid clearance until all GovernanceOS readiness facts are green** for this contract type and required clearances.
D5. **Block bid clearance if Codex flags a cyber posture gap** that cannot be remediated before the deadline.
D6. If no-bid: optionally route to subcontractor / teaming pursuit.
D7. Maintain audit trail: every bid decision logged with who, when, why.

### E. Capture strategy

E1. Generate a one-page brief on the agency, the contracting office, the program.
E2. Identify the incumbent (current contract holder) and their performance history.
E3. Identify likely competitors based on past awards in this NAICS/agency.
E4. Surface the customer's likely real priorities (price-driven? technical? past perf?).
E5. Allow the user to capture **win themes** and **discriminators** at a strategy level (high-level "why us"; full ghost copy is a ProposalOS concern).

### F. Capability + people + partner library

F1. **Capability statement library** — standard pitch documents, versioned, per-domain.
F2. **Past performance library** — past contracts with customer POCs, dollar values, dates, descriptions, CPARS ratings.
F3. **Key personnel library** — resumes, clearances, certs, availability, with version history.
F4. **Teaming partner CRM** — subs, primes, OEMs, consultants — what they bring, **with a reference to the legal documents in GovernanceOS** (MNDA executed yes/no, TA executed for which pursuit). CaptureOS does *not* store the legal docs themselves.

### G. Q&A + amendment tracking

G1. Draft and send clarification questions to the contracting officer.
G2. Ingest government answers and amendments automatically when posted.
G3. Re-diff the compliance matrix and requirements matrix after every amendment.
G4. Surface what changed, who needs to know, what's now non-compliant.
G5. Track acknowledgment of every amendment.

### H. Capture Package export — *the handoff*

H1. Produce a versioned, schema-validated export bundle (Integration Contract #1).
H2. Bundle contents:
   - Opportunity metadata (notice ID, agency, NAICS, set-aside, deadline, contract type, place of performance, est value, submission method)
   - Every solicitation file + every amendment + Q&A history
   - Compliance matrix (with citations to source documents)
   - Requirements matrix (with citations)
   - Pass/fail items and scored evaluation factors
   - Cyber clauses identified + Codex posture snapshot at decision time
   - Capture strategy (agency intel, incumbent intel, competitor intel, customer priorities)
   - Win themes + discriminators (high-level)
   - Selected past performance references (refs to library entries)
   - Selected key personnel (refs to library entries)
   - Teaming partners (refs + GovernanceOS legal-doc state)
   - Bid/no-bid memo + decider + date
   - GovernanceOS readiness facts snapshot at decision time
H3. Push to ProposalOS via API or download as a zip.
H4. Schema is published, versioned, backwards-compatible. Treat it as a public API.

### I. Alerts + notifications

I1. Notify on new matching opportunities (saved-search hits).
I2. Notify on amendments to opportunities you're pursuing.
I3. Notify on approaching deadlines (Q&A cutoff, proposal due date, site visit).
I4. Notify on cyber posture gaps that block a pursuit.
I5. Notify on GovernanceOS readiness gaps that block a pursuit.

### J. Dashboards + reporting

J1. Pipeline view (all pursuits by stage).
J2. Win/loss tracking with reasons (data fed back from ProposalOS award-intake events).
J3. Market trend reports (where is spending going in your NAICS?).
J4. Founder/owner workload view.

---

## How it must behave (non-functional)

- **Multi-tenant with hard isolation.** Row-level security in PostgreSQL; tenant-scoped queries at the ORM layer.
- **CMMC 2.0 Level 2 alignment.** Solicitation files can become CUI; treat all ingested government documents as CUI by default.
- **Role-based access control.** Capture lead, pursuit owner, viewer, exec.
- **Audit logging.** Every solicitation read, every bid decision, every Capture Package export.
- **US data residency.** Commercial cloud (US regions) acceptable in V1; GovCloud as scale and revenue justify.
- **SSO.** Clerk in V1; SAML for enterprise tier later.
- **Idempotent ingestion.** Safe to re-run any data pull.
- **Rate-limit aware.** Every external API call respects limits with exponential backoff.
- **Performance.** Dashboard < 2s, search < 1s, bulk ingestion async.
- **Uptime.** 99.5% V1, 99.9% at scale.

---

## Integration contracts

### Outbound (CaptureOS publishes)

| Contract | Consumer | Content |
|---|---|---|
| **Capture Package** | ProposalOS | Full handoff bundle described in section H above. |
| **Pursuit events** | GovernanceOS | "Bidding on opportunity X with partners Y, Z" — lets GovernanceOS confirm necessary teaming docs are in place. |

### Inbound (CaptureOS consumes)

| Contract | Publisher | Content |
|---|---|---|
| **Cyber Posture** | Codex | SPRS score, CMMC level, 800-171 coverage, gap list. Used in eligibility check and bid/no-bid gate. |
| **Readiness Facts** | GovernanceOS | Accounting system DCAA status, FCL status + level, set-aside eligibility, E-Verify, current reps & certs, executed teaming docs per partner. Used in eligibility check and bid/no-bid gate. |
| **Award Outcomes** | ProposalOS | Win/loss/no-award for past pursuits. Closes the feedback loop into win/loss reporting and market intel. |

---

## External integrations (non-MacTech)

- SAM.gov (Get Opportunities, Entity Management, Exclusions)
- USASpending.gov, FPDS-NG
- SBA DSBS
- SEC EDGAR (financial distress signals on incumbents/competitors)
- Apify (configured scrapers)
- SerpAPI (web augmentation)
- Anthropic / Claude API (intelligence + extraction)
- Voyage embeddings (semantic search across opportunities + capabilities)
- Resend (email)

---

## Data model (high level)

- Tenant
- User + Role
- Saved Search
- Opportunity (with version history for amendments)
- Solicitation Document
- Compliance Item / Requirement Item
- Pursuit (a tenant's stance on an opportunity)
- Bid/No-Bid Decision
- Capability Statement
- Past Performance Record
- Key Personnel
- Teaming Partner Reference (with link to GovernanceOS legal-doc records)
- Question + Answer
- Amendment
- Capture Package (versioned export bundle)
- Audit Event

---

## What it does NOT do

- Write proposal volumes — *ProposalOS*
- Build pricing or do BOE math — *PricingOS*
- Fill out SF 33 / SF 1449 / reps & certs — *ProposalOS pulls from GovernanceOS*
- Run color-team reviews — *ProposalOS*
- Submit anything to a government portal — *human, with ProposalOS submission companion*
- Manage cyber posture — *Codex*
- Hold legal documents (MNDAs, TAs, sub agreements) — *GovernanceOS*
- Manage reps & certs — *GovernanceOS*
- Manage post-award contract execution, CDRLs, invoicing, mods, closeout — *GovernanceOS*

---

## V1 scope (Phase 1, MacTech internal use)

- Sections A, B (B1–B4 only — full eligibility ties to GovernanceOS later), C (compliance + requirements matrices), D (basic), E, F (libraries), G, I (basic alerts), J (basic dashboard).
- Capture Package export schema **defined and versioned** even though ProposalOS doesn't exist yet — design now, mature later.
- B5–B7 (full readiness/posture gating) lights up as Codex and GovernanceOS expose their feeds.
