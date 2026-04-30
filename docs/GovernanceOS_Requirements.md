# GovernanceOS — Requirements Specification

**Version:** 0.1 (draft)
**Audience:** MacTech founders, future engineers, future product partners
**Owner:** Brian (Quality pillar)
**Read first:** `00_Ecosystem_Overview.md`

---

## Purpose

Make and keep the company eligible to do federal work — and run the contract after you win it.

GovernanceOS is the **bookend on either side of the pipeline**:

- **Front bookend** — corporate formation, registrations, accounting system policy, HR/labor compliance, teaming legal documents, reps & certs. This is the "are we ready to bid at all?" layer that CaptureOS gates against.
- **Back bookend** — post-award contract execution, scope changes, reporting, invoicing handoff, closeout, CPARS. This is what runs after ProposalOS submits and the award arrives.

GovernanceOS does *not* find opportunities, write proposals, do pricing math, or manage cyber posture. Those are CaptureOS, ProposalOS, PricingOS, and Codex respectively. GovernanceOS owns everything else that happens *around* a federal contract.

This document is structured to mirror the seven-phase Enterprise GovCon Lifecycle manual that motivates the product, while being explicit about which phase functions belong to GovernanceOS vs. a sibling app.

## Who uses it

- **Compliance lead / COO / General Counsel** — primary user; owns corporate readiness and post-award compliance
- **Contracts administrator** — manages teaming docs, subcontracts, modifications, REAs
- **HR / payroll lead** — owns SCA wage tracking, E-Verify, VETS-4212
- **Finance / accounting lead** — interfaces with timekeeping and accounting systems; owns indirect rate maintenance
- **Capture lead** — read-only consumer of readiness facts (via integration to CaptureOS)
- **Proposal manager** — read-only consumer of reps & certs (via integration to ProposalOS)
- **Executive sponsor** — final approval on registrations, set-aside applications, major contract events

---

## What it does (functional requirements)

### A. Corporate identity vault *(mirrors Manual Phase 1.1, 1.2)*

A1. Articles of incorporation / operating agreement — store, version, and tag clauses relevant to set-asides:
   - Unconditional control clause (for SDVOSB, 8(a), WOSB, HUBZone)
   - Transfer of ownership restraints
   - Officer authority and supermajority overrides
A2. Federal identifier registry: EIN, UEI, CAGE, SAM.gov registration — track issue date, expiration, renewal status.
A3. SAM.gov registration sync — pull current registration state, alert on approaching renewal (annual).
A4. Authorized signatory registry — who can sign what, signature authority limits, refresh dates.
A5. Beneficial ownership / FOCI (Foreign Ownership, Control, or Influence) tracking.
A6. Corporate document audit trail — every change to articles, operating agreement, ownership, officer roles.

### B. Reps & certs management *(mirrors Manual Phase 1.2 — FAR 52.204-7)*

B1. Master Section K reps & certs profile — the single canonical version of the company's representations.
B2. Annual renewal workflow tied to SAM.gov registration cycle.
B3. Per-bid amendment workflow — some certs are bid-specific (e.g., TAA, organizational conflicts).
B4. Audit trail for every change to any rep or cert.
B5. **Publish the current profile to ProposalOS** for auto-fill in every proposal (Integration Contract #3).

### C. Set-aside eligibility tracking *(mirrors Manual Phase 1.1)*

C1. SDVOSB, 8(a), WOSB, HUBZone, VOSB statuses with certification dates and expirations.
C2. Renewal alerts well in advance of expiration.
C3. Affiliation rules monitoring — flag ownership/officer changes that could disqualify a set-aside status.
C4. **Publish set-aside eligibility to CaptureOS** as part of the Readiness Facts feed.

### D. Accounting system governance *(mirrors Manual Phase 2.1 — DCAA)*

D1. SF 1408 readiness checklist (the DCAA Pre-Award Survey) — track completion status.
D2. Indirect rate pool definitions: Fringe, Overhead (OH), General & Administrative (G&A) — with audit history of every change.
D3. FAR 31 allowable vs. unallowable cost policy registry.
D4. Timekeeping policy — daily total-time accounting, supervisor approval, change audit trail. Store the policy; integrate with the timekeeping system (Deltek, Unanet, QuickBooks Time).
D5. Cost-Reimbursement / T&M contract eligibility flag — green only when SF 1408 readiness is current.
D6. **Publish accounting system status to CaptureOS** (Readiness Facts) and **publish indirect rate pools to PricingOS** (Integration Contract #5).
D7. GovernanceOS does **not** replace the accounting system. It holds policy, readiness state, and audit trail; the actual ledger lives in Deltek/Unanet/QuickBooks.

### E. HR + labor compliance *(mirrors Manual Phase 2.3)*

E1. E-Verify enrollment status (FAR 52.222-54).
E2. SCA wage determination tracking per active contract (FAR 52.222-41) — DoL wage-determination version, mapping to labor categories, H&W rate.
E3. Health & welfare benefit tracking aligned to current SCA rates.
E4. Vacation tracking aligned to SCA.
E5. VETS-4212 reporting (annual, due September 30) — capture data, generate filing.
E6. I-9 audit readiness register.
E7. **Publish HR compliance status (E-Verify enrolled, SCA-ready) to CaptureOS** as Readiness Facts.

### F. Teaming + subcontract document vault *(mirrors Manual Phase 3)*

F1. **MNDA** library — templates + executed copies, by counterparty.
F2. **Teaming Agreement (TA)** library — templates + executed TAs, by pursuit and counterparty, with explicit prime/sub scope-split tracking (for FAR 52.219-14 Limitations on Subcontracting compliance).
F3. **Subcontract Agreement** library — templates + executed agreements + flow-down clause version.
F4. **FAR / DFARS flow-down clause registry** — versioned, auto-updated as regs change, attached to every subcontract.
F5. Organizational Conflict of Interest (OCI) screening workflow.
F6. Affiliation analysis (size standard implications of partnerships).
F7. **Publish executed-document state to CaptureOS** — for any partner referenced in a pursuit, surface "MNDA executed yes/no, TA executed yes/no, subcontract executed yes/no."
F8. CaptureOS holds the **partner CRM** (capture relevance); GovernanceOS holds the **legal documents** (record of state).

### G. Facility + personnel clearance tracking *(mirrors Manual Phase 4 risk gates)*

G1. Facility Clearance (FCL) record — status, level, sponsor agency, expiration, CSO contact.
G2. Cleared personnel registry — clearance level, investigation date, periodic reinvestigation due, agency.
G3. DD254 generation workflow — Contract Security Classification Specification for subs.
G4. **Publish FCL status to CaptureOS** (Readiness Facts).

### H. Pre-award readiness dashboard

H1. Single-pane view of "are we ready to bid this kind of contract?" with green/red flips on:
   - Approved DCAA accounting system?
   - Required FCL?
   - Required CMMC level (pulled from **Codex**)?
   - Set-aside eligibility match?
   - E-Verify enrolled?
   - Reps & certs current?
   - Required teaming docs in place per partner?
H2. Per-contract-type filter (FFP / CR / T&M / IDIQ / GWAC).
H3. Drill-through to the underlying record for any red flag.
H4. **This dashboard's data is the Readiness Facts feed** consumed by CaptureOS (Integration Contract #2).

### I. Award intake *(mirrors Manual Phase 5 entry)*

I1. **Receive "we won" event from ProposalOS** (Integration Contract #7).
I2. Create contract record: contract number, contracting officer, awarded value, period of performance, CLIN structure, contract type, key clauses, prime/sub split.
I3. Initiate post-award workflow (sections J–N below).

### J. Contract execution governance *(mirrors Manual Phase 5)*

J1. **Limitation of Cost (FAR 52.232-20) / Limitation of Funds (FAR 52.232-22)** tracking — burn-rate monitoring, 75% threshold alert, KO notification letter generation.
J2. **Constructive Change detection workflow** — when a COR (Contracting Officer's Representative) requests out-of-scope work:
   - Halt-work checklist
   - 30-day written notice to KO template (FAR 52.243-1 / 52.243-2)
J3. **Request for Equitable Adjustment (REA)** preparation — DCAA-compliant pricing for changed work.
J4. Modification log — every contract mod, who signed, what changed.

### K. CPSR readiness — Contractor Purchasing System Review *(mirrors Manual Phase 5.2)*

K1. Triggers when prime sales exceed $50M (FAR Part 44).
K2. Purchase record management with competition set tracking (3+ quotes).
K3. Price reasonableness determinations.
K4. Subcontractor responsibility checks — SAM exclusions check (debarment screen) before any award.
K5. FAR flow-down audit per executed subcontract (cross-reference against the flow-down clause registry from F4).
K6. Purchasing manual versioning + change audit.

### L. Reporting hub *(mirrors Manual Phase 6)*

L1. **eSRS** (Electronic Subcontracting Reporting System) — semi-annual subcontracting reports (FAR 52.219-9). Applies to large-business primes.
L2. **SAM.gov Executive Compensation** — annual top-5 executive comp reporting (FAR 52.204-10).
L3. **VETS-4212** — annual veteran employment metrics, due September 30 (FAR 52.222-37).
L4. **Subcontracting Plan tracking** — when a Small Business Subcontracting Plan is required, track commitments vs. actuals.
L5. Reporting calendar — single view of every upcoming federal report with deadline + responsible owner.

### M. Invoicing handoff *(mirrors Manual Phase 6.1 — WAWF / IPP)*

M1. WAWF (Wide Area Workflow — DoD) and IPP (Invoice Processing Platform — civilian) invoice prep templates aligned to CLIN structure.
M2. Pull invoice line items from the timekeeping/accounting system (Deltek/Unanet integration).
M3. Mark final invoices "FINAL" per closeout requirements.
M4. GovernanceOS does **not** replace the invoicing system. It formats per-CLIN, validates against the contract, and hands the prepared invoice to the customer's accounting system or directly to WAWF/IPP for submission.

### N. Closeout workflow *(mirrors Manual Phase 7.2 — FAR 4.804)*

N1. Incurred Cost Submission (ICS) tracking for CR/T&M contracts.
N2. Final invoice workflow with "FINAL" marking and closeout audit.
N3. Release of Claims execution — government absolved of future liabilities; explicitly preserve any unresolved REA rights.
N4. CPARS (Contractor Performance Assessment Reporting System) — capture government rating, archive.
N5. **Push performance lessons learned to CaptureOS** so future pursuits in the same agency/program are smarter.

### O. Audit trail + governance dashboards

O1. Every governance event logged — registration changes, rep & cert renewals, signed teaming docs, accounting policy changes, threshold alerts, REAs, mods, reports, closeout events.
O2. Audit-ready exports per phase (formation, compliance infrastructure, teaming, post-award, reporting, closeout).
O3. Pillar dashboards: Corporate / Compliance / Contract Operations / Reporting / Closeout.

---

## How it must behave (non-functional)

- **CMMC 2.0 Level 2 alignment.** Some governance workflows (DD254 generation, FCL records, contract specifics) handle CUI; design assumes CUI everywhere.
- **Multi-tenant with hard isolation.** Customer's corporate records, teaming docs, and contract files never cross.
- **Document retention rules.** FAR-driven retention periods (often 3–6 years post final payment) enforced automatically.
- **Audit log of every change.** Document edits, signatory actions, certification renewals, threshold breaches.
- **Role-based access control.** Teaming docs and contract specifics are restricted; not every user sees every contract.
- **E-sign integration** (DocuSign / Adobe Sign) for teaming docs, subcontracts, signatory authority pages.
- **Calendar integration** for renewal alerts (SAM.gov annual, VETS-4212 annual, eSRS semi-annual, set-aside expirations, SCA wage determination updates).
- **Eventual GovCloud residency.** Contract files and CUI handling pushes GovernanceOS toward GovCloud earlier than CaptureOS.

---

## Integration contracts

### Outbound (GovernanceOS publishes)

| Contract | Consumer | Content |
|---|---|---|
| **Readiness Facts** (Contract #2) | CaptureOS | Accounting system DCAA status, FCL status + level, set-aside eligibility, E-Verify status, reps & certs currency, teaming-doc state per partner. Used in CaptureOS eligibility check and bid/no-bid gate. |
| **Reps & Certs Feed** (Contract #3) | ProposalOS | Current Section K profile + authorized signatory list. Auto-fills proposal forms. |
| **Indirect Rates + Rate Cards** (Contract #5) | PricingOS | Approved fringe / OH / G&A pools, labor categories, blended/burdened rates. Used by PricingOS to price proposals correctly. |

### Inbound (GovernanceOS consumes)

| Contract | Publisher | Content |
|---|---|---|
| **Cyber Posture** (Contract #4) | Codex | SPRS score, CMMC level, 800-171 coverage, gap report. Displayed on the readiness dashboard; gates contract types that require specific CMMC levels. |
| **Pursuit Events** | CaptureOS | "Bidding on opportunity X with partners Y, Z" — lets GovernanceOS flag missing teaming docs in time to execute them before bid. |
| **Award Intake** (Contract #7) | ProposalOS | Awarded contract details — number, KO, value, period of performance, CLINs, key clauses. Triggers the post-award lifecycle (sections I–N). |

---

## External integrations (non-MacTech)

- **SAM.gov** — registration sync, reps & certs sync, exclusion list pulls
- **DocuSign / Adobe Sign** — teaming docs, subcontracts, signatory authority pages
- **Deltek Costpoint / Unanet / QuickBooks** — accounting system reference (read-only); GovernanceOS holds policy, never the ledger
- **Deltek Time / Unanet / QuickBooks Time** — timekeeping system reference (read-only); GovernanceOS holds policy
- **WAWF (Wide Area Workflow — DoD)** and **IPP (civilian)** — invoice submission destinations
- **DIBNet** — cyber incident reporting handoff to Codex; GovernanceOS surfaces the requirement, Codex performs the report
- **CPARS** — pull awarded ratings into the contract record

---

## Data model (high level)

- Tenant
- Corporate Entity (articles, operating agreement, version history)
- Federal Identifier (UEI, CAGE, EIN)
- Set-Aside Status + Renewal Schedule
- Reps & Certs Profile + Version
- Authorized Signatory
- Accounting System Profile + DCAA Readiness Run
- Indirect Rate Pool + Rate Card
- Labor Category
- Timekeeping System Reference
- HR Compliance Item (SCA wage det., E-Verify enrollment, I-9 audit, VETS-4212 filing)
- Teaming Document (MNDA / TA / Subcontract) + Counterparty
- Flow-Down Clause Library + Version
- Facility Clearance + Personnel Clearance
- Awarded Contract + CLIN + Modification + Mod History
- LOC/LOF Threshold Alert
- REA / Change Order
- Purchase Record + Competition Set
- Reporting Submission (eSRS, VETS-4212, Exec Comp, Subcontracting Plan)
- Invoice Draft
- Closeout Run + ICS + Release of Claims + CPARS Record
- Audit Event

---

## What it does NOT do

- Hunt or qualify federal opportunities — *CaptureOS*
- Make the bid/no-bid decision — *CaptureOS* (GovernanceOS gates it via Readiness Facts; the workflow lives in CaptureOS)
- Write proposal volumes — *ProposalOS*
- Build pricing math, BOE, or cost narrative — *PricingOS* (GovernanceOS publishes the *rates*; PricingOS does the *math*)
- Manage cyber posture — *Codex* (GovernanceOS displays it; never stores it)
- Replace the accounting system or timekeeping system — *Deltek / Unanet / QuickBooks* (GovernanceOS holds policy + readiness state, integrates for reads)
- Auto-click the government submit button at PIEE / SAM / WAWF — *human* (GovernanceOS prepares; human submits)
- Hold capture-relevant partner relationships — *CaptureOS holds the partner CRM*; GovernanceOS holds the *signed legal documents* between the parties

---

## V1 scope — Phase 3 of the ecosystem build

**V1 (front bookend) — corporate readiness:**

- A. Corporate identity vault
- B. Reps & certs management with feed to ProposalOS (even before ProposalOS is live, expose the API)
- C. Set-aside eligibility tracking
- D. Accounting system governance (policy + readiness; defer indirect-rate publish to PricingOS until PricingOS is real)
- E. HR + labor compliance (basic — E-Verify, VETS-4212, SCA tracking)
- F. Teaming + subcontract document vault
- G. FCL + clearance tracking
- H. Pre-award readiness dashboard with **Readiness Facts feed to CaptureOS** (this is the highest-leverage integration in V1)
- O. Audit trail + dashboards

**V2 (back bookend) — post-award operations:**

- I. Award intake from ProposalOS
- J. Contract execution governance (LOC/LOF, REAs, mods)
- K. CPSR readiness
- L. Reporting hub (eSRS, VETS-4212, Exec Comp)
- M. Invoicing handoff
- N. Closeout

V2 lights up when MacTech wins its first contract — there's no point building post-award workflows before there's an award to manage.

---

## Why GovernanceOS as a separate app, not a CaptureOS module

1. **Different data sensitivity.** Teaming docs, contract specifics, executed subcontracts, REAs — these are CUI-class artifacts with retention rules that exceed what CaptureOS needs. GovernanceOS will graduate to a stricter security boundary (FedRAMP Moderate, eventually GovCloud) on a faster timeline than CaptureOS.

2. **Different buyer.** CaptureOS is for the BD/capture lead. GovernanceOS is for the COO/GC/compliance lead. In a small DIB, that's the same person; in a mid-size DIB, it's two people; in an enterprise, it's two departments. Splitting the SKU now lets each app price and message correctly.

3. **Different lifecycle.** Capture is per-pursuit (transient). Governance is per-contract and per-corporate-state (long-lived). One database mixing both is a recipe for retention/access-control complexity.

4. **Different competitive set.** CaptureOS competes with GovTribe, GovWin, EZGovOpps, Highergov. GovernanceOS competes (loosely) with Unanet, Deltek's compliance modules, parts of Procurement Sciences. Different competitive narrative requires different positioning.

5. **The ecosystem benefits from cleanly defined contracts.** Forcing GovernanceOS to publish Readiness Facts and Reps & Certs as versioned APIs makes the whole platform composable — even external customers who use a third-party governance tool can integrate.
