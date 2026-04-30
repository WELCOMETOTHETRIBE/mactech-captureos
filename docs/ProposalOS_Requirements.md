# ProposalOS — Requirements Specification

**Version:** 0.1 (draft)
**Audience:** MacTech founders, future engineers, future product partners
**Read first:** `00_Ecosystem_Overview.md`

---

## Purpose

Turn a Capture Package from CaptureOS into a winning, compliant, submittable proposal — and hand the human a packaged file ready to upload at the government portal.

ProposalOS is the **middle of the pipeline**. It consumes the Capture Package from CaptureOS, the reps & certs feed from GovernanceOS, the cyber posture from Codex, and the finished price volume from PricingOS. It produces a single submission bundle and pushes the award outcome back upstream.

ProposalOS is a future product — it does not exist yet. This document defines what it will be when MacTech (or a customer) needs full proposal authoring inside the platform.

## Who uses it

- **Proposal manager** — primary user; runs the proposal effort
- **Volume lead** — owns one volume (technical, management, staffing, past perf, cyber, executive summary)
- **Writer / SME** — drafts content within an assigned section
- **Color-team reviewer** — provides structured feedback at pink/red/gold gates
- **Pricing analyst** — works in PricingOS; ProposalOS pulls their finished volume in
- **Capture lead** — read-only; their handoff already happened via the Capture Package
- **Executive sponsor** — final approval before submission

---

## What it does (functional requirements)

### A. Capture Package import

A1. Pull a **Capture Package** from CaptureOS via API (Integration Contract #1).
A2. Or accept a manual upload of the same package format (e.g., from an external customer not on CaptureOS).
A3. Validate the package against the published schema (completeness, version, freshness).
A4. Surface any gaps the proposal team needs to fill before kicking off (missing past perf citations, missing key personnel resumes, etc.).

### B. Proposal schedule + volume management

B1. Generate a proposal schedule backwards from the deadline (extracted from Capture Package).
B2. Pre-populate color-team gates (pink team, red team, gold team) and milestone reviews.
B3. Assign volume owners, section owners, and reviewers.
B4. Track status per section (not started → drafting → in review → final).
B5. Surface critical path and slipping items.

### C. Volume drafting workspace

C1. Per-volume editor for: technical, management, staffing, transition, QC, risk, cybersecurity, small business participation, executive summary, cover letter.
C2. Each section is **mapped to one or more compliance matrix items** from the imported Capture Package — the matrix is the spine.
C3. AI-assisted drafting from compliance items + win themes + capability content.
C4. Concurrent editing with version history.
C5. Comment threads tied to specific paragraphs.
C6. Lock during reviews.

### D. Win theme + discriminator workshop

D1. Consume the high-level win themes from the Capture Package.
D2. Translate them into per-volume themes and per-section ghost copy.
D3. Pull through every volume so messaging is consistent.

### E. Resume + letter-of-commitment generation

E1. Generate per-pursuit resumes from the CaptureOS key personnel library, tailored to the SOW/PWS.
E2. Generate letters of commitment for partners.
E3. E-sign integration (DocuSign / Adobe Sign) for partner LOCs.

### F. Past performance volume builder

F1. Pull selected past performance from the Capture Package (which references the CaptureOS library).
F2. Format per the solicitation's rules (page limits, ordering, fields required).
F3. Auto-fill customer POCs, contract numbers, values, dates from the source records.

### G. Cybersecurity narrative generator

G1. Pull current cyber posture from **Codex** (Integration Contract #4).
G2. Generate the cybersecurity volume aligned to the cyber clauses identified in the Capture Package.
G3. Flag posture gaps that need closing before submission and route them back to the cyber lead in Codex.

### H. Form fill — Section K and government cover sheets

H1. Pull the **reps & certs profile from GovernanceOS** (Integration Contract #3).
H2. Auto-populate Section K reps & certs.
H3. Auto-populate SF 33, SF 1449, SF 18 cover/offer forms.
H4. Generate signature pages for the right authorized signatory (signatory list also from GovernanceOS).

### I. Color-team review workflow

I1. Pink team — early structure + win-strategy review.
I2. Red team — review against the actual evaluation criteria from Section M (in the Capture Package).
I3. Gold team / final review.
I4. Track review comments, owner, status, resolution.
I5. Block progression until prior gate is closed.

### J. Compliance audit engine

J1. Run against the compliance matrix imported from CaptureOS — every "shall" must map to a section that addresses it.
J2. Flag every unaddressed requirement, every page-limit overrun, every missing form, every missing acknowledged amendment.
J3. Re-run after every amendment is applied (re-fetch Capture Package version if amended).

### K. Format + page-limit compliance

K1. Check fonts, margins, page count per volume, file-name conventions.
K2. Verify all amendments are acknowledged.
K3. Verify all signatures present.

### L. Pricing volume integration

L1. **Receive the finished price/cost volume from PricingOS** (Integration Contract #6).
L2. Attach to the package — never edit pricing inside ProposalOS.
L3. Verify price volume formatting matches solicitation rules.

### M. Final package assembly

M1. Combine all volumes, forms, and pricing into the submission bundle.
M2. Generate a final compliance report (audit engine output).
M3. Generate the proof-of-submission template (timestamp, files, hashes).

### N. Submission companion

N1. Present the human with a **submission checklist** — where to upload, which files, in what order, before what time.
N2. Capture proof: confirmation numbers, timestamps, screenshots, emails.
N3. Save the submitted bundle as the immutable record.
N4. ProposalOS does **not** click submit. Always a human in front of the government portal.

### O. Post-submission tracking

O1. Track receipt confirmation from the government.
O2. Track clarification requests from the contracting officer; draft responses, send them.
O3. Manage Final Proposal Revision (FPR) cycles if discussions are opened.
O4. Capture debrief content if the bid loses.

### P. Award intake handoff

P1. **On award notice, push the award event to GovernanceOS** (Integration Contract #7) — contract number, KO, value, period of performance, CLINs, key clauses.
P2. **Push outcome (win/loss/no-award) back to CaptureOS** so capture intel and win/loss dashboards stay current.
P3. Push debrief lessons learned back to CaptureOS for future pursuits in similar agencies/programs.

---

## How it must behave (non-functional)

- **CMMC 2.0 Level 2 / FedRAMP Moderate posture.** ProposalOS handles CUI and source-selection-sensitive content; it graduates to a stricter security enclave faster than CaptureOS does.
- **Multi-tenant with per-pursuit sub-isolation.** Even within one tenant, pursuits are isolated; reviewers only see what they're assigned.
- **Document retention + destruction.** Meet government retention rules; auto-purge on schedule.
- **Full audit log.** Every edit, every review comment, every export, every download.
- **Version control + diff per draft.** Restore any prior version.
- **Concurrent editing** with locking during review gates.
- **Encryption at rest and in transit** with FIPS-validated cryptography.
- **E-sign integration** for partner agreements and signatory pages.

---

## Integration contracts

### Outbound (ProposalOS publishes)

| Contract | Consumer | Content |
|---|---|---|
| **Award Intake** | GovernanceOS | Contract number, KO, value, period of performance, CLIN structure, key clauses, awarded prime/sub split. Triggers GovernanceOS post-award lifecycle. |
| **Award Outcomes** | CaptureOS | Win, loss, or no-award event with reasons and debrief notes. Closes the loop on capture intel. |

### Inbound (ProposalOS consumes)

| Contract | Publisher | Content |
|---|---|---|
| **Capture Package** | CaptureOS | Full handoff bundle including compliance matrix, requirements matrix, capture strategy, etc. |
| **Reps & Certs Feed** | GovernanceOS | Current Section K profile + authorized signatory list. |
| **Cyber Posture** | Codex | SPRS score, CMMC level, 800-171 controls + gap report. |
| **Price Volume** | PricingOS | Finished, formatted cost/price artifact. |

---

## External integrations (non-MacTech)

- DocuSign / Adobe Sign (e-sign)
- DOCX / PDF rendering
- Microsoft Word / Google Docs interoperability for export
- (Eventually) browser extension companion to ease — but never automate — submission portal uploads (PIEE, SAM.gov, agency portals)

---

## Data model (high level)

- Tenant
- Pursuit (mirrored from CaptureOS, kept in sync via Capture Package version)
- Capture Package (imported, versioned)
- Proposal (one per pursuit)
- Volume
- Section (mapped to compliance matrix items)
- Draft Version
- Review Gate + Review Comment
- Resume + Letter of Commitment
- Form Submission (SF 33 etc.)
- Compliance Audit Run
- Submission Bundle
- Receipt + Clarification + Final Proposal Revision
- Award Notice
- Audit Event

---

## What it does NOT do

- Hunt or qualify opportunities — *CaptureOS*
- Make the bid/no-bid decision — *CaptureOS*
- Build pricing math, indirect rates, or BOE — *PricingOS*
- Manage cyber posture — *Codex*
- Manage reps & certs as a record of corporate state — *GovernanceOS* (ProposalOS *fills in* per submission)
- Hold legal documents (MNDAs, TAs, signed subcontracts) — *GovernanceOS*
- Auto-click the submit button at PIEE / SAM / agency portals — *human*
- Manage post-award contract execution, CDRLs, invoicing, mods, closeout — *GovernanceOS*

---

## V1 scope

ProposalOS is **not Phase 1**. Build it when:

- CaptureOS reliably produces a complete, schema-valid Capture Package.
- GovernanceOS exposes the reps & certs feed.
- A first customer (MacTech itself or a paying DIB) is ready to author a real proposal in the platform.

V1 functional scope when triggered: A, B, C, F, G, H, I, J, K, M, N, P. Defer D (full win-theme workshop), E (e-sign LOCs), L (full PricingOS integration — accept manual price volume upload first), O (post-submission FPRs).
