# MacTech Playbook — How This Tool Wins Contracts for MacTech

**This document is Phase 1's governing spec.** Everything else in `/docs` is reference; this is what Claude Code builds *for*. When a design question comes up, the answer is whatever helps MacTech win its next contract fastest.

Multi-tenant SaaS capabilities exist in the architecture from day one, but they are scaffolding. The product MacTech uses internally every day is the product we're shipping first.

---

## 1. The four founders and what they need every morning

The platform has four primary users. Not personas — actual people with specific capture responsibilities. Every feature ships against at least one of their named workflows.

### Patrick Caruso — Security (Primary NAICS: 541519, 541512, 541513, 518210)

**What he needs from the platform:**
- Every new Sources Sought, Presolicitation, and Combined Synopsis/Solicitation posted to SAM.gov where NAICS in {541519, 541512, 541513, 518210, 541715} AND (set-aside is SDVOSB, SDVOSB sole-source, small business total, or unrestricted with SDVOSB preference).
- Within those, surface anything mentioning: RMF, ATO, ConMon, STIG, CMMC, NIST 800-171, NIST 800-53, FedRAMP, SCA, security control assessment, POA&M, cyber, information assurance, IA, cybersecurity, vulnerability assessment, penetration testing.
- For each opportunity: incumbent name (from USASpending lookup), current contract end date, incumbent's prior performance indicators (we infer from CPARS / award history).
- One-click draft of the Sources Sought response, pre-populated with MacTech's security capability statements and Patrick's bio.
- Compliance-matrix auto-generation from Section L/M when a full solicitation drops.

**Morning digest for Patrick, 6am ET daily:**
- Up to 5 new opportunities matched + scored above threshold 70
- For each: one-line "why Patrick" (e.g., "CMMC L2 ATO support for Navy — direct match to your CMMC 2.0 L2 and FedRAMP Moderate alignment")
- "Pursue / Skip / More Info" buttons that move the opportunity into the pipeline with one click

### James Adams — Infrastructure (Primary NAICS: 518210, 541330, 541512, 541513)

**What he needs:**
- Opportunities in {518210, 541330, 541512, 541513, 541511, 561210} mentioning: data center, virtualization, cloud migration, IaC, infrastructure as code, network architecture, storage, backup, disaster recovery, hyperconvergence, VMware, AWS, Azure, GovCloud, containerization, Kubernetes.
- Special interest: contract vehicles for infrastructure work — SEWP V, GSA 2GIT, ITES-SW2, any NETCENTS task orders.
- Scale / ceiling indicators — James's sweet spot is $500k–$5M individual task orders, not sub-$100k micro-purchases.

**Morning digest for James:** Same format as Patrick's. Also a weekly "SEWP V / ITES tasks" rollup on Mondays.

### Brian MacDonald — Quality (Primary NAICS: 541380, 541614, 541611)

**What he needs:**
- Opportunities in {541380, 541614, 541611, 541618} mentioning: ISO 9001, ISO 17025, metrology, calibration, audit, quality management, QMS, process improvement, accreditation, laboratory, test and measurement.
- Any DoD opportunity requiring ISO-certified processes, independent testing, or third-party audit support.
- Standout signal: opportunities where MacTech's ISO 17025 alignment is a differentiator — these are rare and high-value.

**Morning digest for Brian:** Lower volume expected (quality NAICS are narrower). When a match shows up, treat it as high-priority.

### John Milso — Governance (Primary NAICS: 541110, 541611, 541618)

**What he needs:**
- Opportunities in {541110, 541611, 541618, 541199} mentioning: legal services, contract review, compliance, M&A, due diligence, risk advisory, corporate governance, regulatory.
- Subcontract opportunities where MacTech is being considered as a sub — John vets the teaming agreement before we sign.
- Critical role: exclusions screening and compliance review gate before any pursuit moves to "Submit" stage.

**Morning digest for John:** Fewer direct-pursuit opportunities; more "advise the team" touchpoints. Separate weekly feed: "Pursuits entering the Propose stage that need your legal review."

---

## 2. MacTech's specific NAICS targeting configuration

These go into the seed data exactly as specified. The scoring engine uses them as the baseline weights.

### Primary pursuit codes (scoring boost: +25 pts)
`541519, 541512, 518210, 541513, 541611, 541330, 541380, 541110`

### Secondary pursuit codes (scoring boost: +15 pts)
`541618, 541511, 541614, 611420, 611430, 541199, 561621, 561210, 541715, 541690, 541990, 611710`

### Automatic founder routing rules

| If opportunity NAICS is one of... | Default owner | Alt owner |
|---|---|---|
| 541519, 541512, 518210, 541513, 541715 | Patrick | James |
| 541330, 541511, 561210 | James | Patrick |
| 541380, 541614 | Brian | — |
| 541611, 541618 | *Split by keyword:* legal/compliance → John; quality/ops → Brian | — |
| 541110, 541199 | John | — |
| 541690, 541990, 611420, 611430, 611710, 561621 | *Keyword-driven:* security → Patrick; infra → James; quality/audit → Brian; legal/gov → John | — |

---

## 3. MacTech's set-aside filter profile

MacTech is **SDVOSB (pending)** and **veteran-owned**. Default SAM.gov query set-aside filters include:

- `SDVOSBC` — SDVOSB Set-Aside
- `SDVOSBS` — SDVOSB Sole Source
- `VSA` — Veteran-Owned Small Business Set-Aside
- `VSS` — VOSB Sole Source
- `SBA` — Total Small Business Set-Aside
- `SBP` — Partial Small Business Set-Aside
- `SB` — Small Business
- *(unrestricted — worth scanning but deprioritized)*

Exclude by default (low fit for a 4-person firm early-stage):
- `8A`, `8AN` — 8(a) set-asides (MacTech isn't 8(a) certified)
- `HZC`, `HZS` — HUBZone (not certified)
- `WOSB`, `EDWOSB` — WOSB (not applicable)

The SDVOSB (pending) status is material: until certification is confirmed, opportunities flagged as SDVOSB set-aside should include a visible "certification-pending" warning on the pursuit record.

---

## 4. Target agencies (for Apify forecast scraping — Phase 2)

Ranked by MacTech's likely win probability based on NAICS fit and practice area:

1. **DISA** — Defense Information Systems Agency. Cyber, network, data center.
2. **Navy — NIWC Atlantic & NIWC Pacific** — Information warfare, cyber, systems engineering.
3. **DoD OSBP + service OSBPs** — Small Business Offices with SDVOSB pipelines.
4. **Department of Veterans Affairs (VA)** — Strong SDVOSB preference, cyber + infrastructure.
5. **Department of Homeland Security (DHS)** — CISA cyber, infrastructure modernization.
6. **Army — PEO C3T, ACC** — Network modernization, cyber.
7. **Air Force — AFLCMC, SSC** — Cyber, space domain IT.
8. **GSA** — Federal Acquisition Service, 18F, TTS (civilian cyber infrastructure).

Apify actors should be built in this order. Navy + VA are the sweet spot: strong SDVOSB culture, steady cyber + infrastructure pipeline.

---

## 5. The dashboard — what MacTech sees when they log in

Dashboard opens to a **single screen** called "This Week." Every other screen is secondary. Built against real MacTech use, not generic SaaS.

### Top section — Pipeline pulse (full width)

Horizontal kanban preview: counts in each stage (Lead / Qualify / Pursue / Propose / Submit / Won / Lost) with live totals. Clickable to drill in.

```
[ Lead: 12 ] → [ Qualify: 4 ] → [ Pursue: 2 ] → [ Propose: 1 ] → [ Submit: 0 ] → [ Won YTD: — | Lost YTD: — ]
                                                                                   Pipeline value: $X.XM
```

### Left column — Today's priority

"Top 5 scored opportunities posted in the last 48 hours." For each:
- Agency · office · NAICS · score (0-100)
- Title (truncated to 80 chars)
- Deadline countdown
- Assigned founder avatar
- Quick actions: Pursue • Skip • Draft Response

Zero clicks to see what matters. One click to commit to a pursuit.

### Right column — Deadline wall

Pursuits with response deadlines in the next 14 days, sorted ascending. Color-coded:
- Red: < 72 hours
- Amber: 72h – 7 days
- Neutral: 7 – 14 days

Each row: opportunity title · stage · owner · deadline with exact H/M remaining. One-click jump to the pursuit.

### Bottom row — Four founder cards

One card per founder showing:
- Active pursuits owned
- Pursuits awaiting their review/input
- Unread digest count

Clicking a card filters "This Week" to that founder's view.

### Secondary screens

- **Opportunities** — full scored feed with filters (already specified in PRD)
- **Pipeline** — full kanban with pursuit detail
- **Library** — capability statements + past performance + teaming partners
- **Insights** — MacTech-specific analytics (§10 below)
- **Settings** — founders, NAICS, saved searches, API keys, integrations

---

## 6. Pursuit detail page — the capture work surface

When a founder clicks into a pursuit, they see the full capture context on one page, organized by what they need to do next. This is the deepest-value screen in the product.

Layout (top to bottom):

**Header strip**
- Opportunity title, agency, NAICS, set-aside, solicitation number, posted date, response deadline, days-remaining countdown
- Stage pill (Lead / Qualify / Pursue / Propose / Submit / Won / Lost) with stage-change action
- Owner (assigned founder) with reassign action
- Exclusions status (green/yellow/red — see §9)

**Left column — The opportunity itself**
- Full description from SAM.gov (collapsible)
- Attached solicitation docs (upload + parsed preview)
- AI-generated "Why this matters for MacTech" paragraph
- Parsed requirements (when solicitation is attached)

**Center column — The capture work**
- **Incumbent intelligence panel** — who has it now, when does it expire, their past performance signals, our competitive position
- **Capability match panel** — top 3 of MacTech's capability statements surfaced by semantic similarity
- **Past performance match panel** — top 3 past-performance entries relevant to this scope
- **Teaming panel** — suggested sub/prime partners from our network, if applicable
- **Compliance matrix** — once solicitation is uploaded, AI-generated Section L/M requirements with owner-assignment

**Right column — Actions and activity**
- "Draft Sources Sought response" button (for Sources Sought only)
- "Generate compliance matrix" button (for full solicitations)
- "Screen exclusions" button (green if clean, red with detail if hit)
- Notes — free text per founder
- Activity feed — every action on this pursuit, auditable

---

## 7. The API integration map — what actually fires for MacTech

This is the Phase 1 integration surface, grounded in what MacTech needs day one. Everything references `docs/DATA_SOURCES.md` for endpoint details.

### Every 2 hours during business days (6am–8pm ET, Mon–Fri):

```
SAM.gov Get Opportunities API
├── for each of MacTech's 20 NAICS codes (batched if API supports)
├── postedFrom = last_successful_run
├── typeOfSetAside = [SDVOSBC, SDVOSBS, VSA, VSS, SBA, SBP, SB]
└── results upserted into opportunities_raw keyed by noticeId
```

### Every 6 hours off-hours and weekends:

Same call, lower cadence.

### For each newly-ingested opportunity (event-driven, within 10 minutes of ingest):

```
1. Voyage embeddings
   └── embed description → opportunities_raw.embedding

2. USASpending.gov API
   ├── POST /search/spending_by_award/
   │   filters = {naics: opp.naics, agency: opp.agency, poc_end_date: ±24mo of opp.posted_at}
   └── result → opportunities_enriched.incumbent_*

3. SAM.gov Exclusions API (on incumbent UEI)
   └── cache → exclusions_cache.is_excluded

4. SAM.gov Entity API (on soliciting office UEI if distinct)
   └── cache → entities table

5. Claude Agent SDK invocation (scoring)
   └── for tenant 'mactech':
       compute score(opp)
       draft why_it_matters paragraph
       suggest assigned_founder_slug
       output → opportunity_scores (MacTech tenant)
```

### On solicitation document upload (user-triggered):

```
1. Parse PDF/DOCX → documents.parsed_content

2. Claude Agent SDK invocation (compliance matrix)
   └── input: parsed_content + pursuit context
       output: ComplianceMatrix schema JSON
       persist: compliance_matrices table
```

### On "Draft Sources Sought response" click (user-triggered):

```
Claude Agent SDK invocation (drafting)
├── input bundle:
│   ├── opportunity description
│   ├── top-3 matching capability statements (pgvector lookup)
│   ├── top-3 matching past performance entries
│   ├── founder bio for assigned owner (from founders.json)
│   └── MacTech boilerplate (company overview, SDVOSB statement, points of contact)
├── session persistence: resume pursuit.agent_session_id if exists, else create new
└── output: SourcesSoughtDraft schema JSON → editable in web app
```

### On pursuit stage change to "Submit" (user-triggered, gated):

```
1. SAM.gov Exclusions API — re-check all parties (MacTech + any subs/teaming partners)
   └── if any exclusion hit, block transition and alert John (governance)

2. Final compliance check — require compliance_matrix.status == 'complete' before advance
```

### Daily 6am ET (Celery Beat):

```
Morning digest (one per founder)
├── query opportunity_scores where scored_at > 24h ago
├── filter by founder.slug = opp.assigned_founder_slug
├── top 5 by score
└── email send via SMTP/Postmark
    subject: "[MacTech Capture] <n> new <founder-first-name> picks for <date>"
```

### Weekly Monday 6am ET:

- Pipeline rollup email to all 4 founders: pursuits by stage, deadlines, value
- Vehicle forecast rollup (Phase 2): agency forecast hits from Apify crawls

---

## 8. MacTech-specific configuration (seed this in Phase 1)

These values are baked into the Phase 1 seed migration so MacTech has a working configuration from the first boot. This goes into a `config/mactech_tenant_defaults.yml` consumed by the seed script.

```yaml
tenant:
  slug: mactech
  name: MacTech Solutions LLC
  plan: internal
  uei: <TO BE FILLED BY BRIAN>
  cage_code: <TO BE FILLED BY BRIAN>
  sdvosb_status: pending
  naics:
    primary: [541519, 541512, 518210, 541513, 541611, 541330, 541380, 541110]
    secondary: [541618, 541511, 541614, 611420, 611430, 541199, 561621, 561210, 541715, 541690, 541990, 611710]
  set_aside_filter:
    include: [SDVOSBC, SDVOSBS, VSA, VSS, SBA, SBP, SB]
    scan_unrestricted: true
    exclude: [8A, 8AN, HZC, HZS, WOSB, EDWOSB]
  target_agencies:
    tier_1: [DISA, NIWC Atlantic, NIWC Pacific]
    tier_2: [DoD OSBP, Department of Veterans Affairs, Department of Homeland Security]
    tier_3: [Army PEO C3T, Air Force AFLCMC, GSA]
  value_ceiling_sweet_spot:
    min: 100000
    max: 10000000
  frameworks_claimed:
    - CMMC 2.0 Level 2 (compliance aligned)
    - NIST CSF 2.0
    - NIST RMF
    - FedRAMP Moderate (design aligned)
    - SOC 2 Type I (internal readiness)

saved_searches:
  - name: Patrick — Security daily
    owner_slug: patrick-caruso
    filters:
      naics: [541519, 541512, 518210, 541513, 541715]
      keywords: [RMF, ATO, ConMon, STIG, CMMC, NIST 800-171, NIST 800-53, FedRAMP, cybersecurity, IA]
      set_asides: [SDVOSBC, SDVOSBS, VSA, VSS, SBA, SBP, SB]
    alert_threshold: 70
    alert_channels: [email]
  - name: James — Infrastructure daily
    owner_slug: james-adams
    filters:
      naics: [518210, 541330, 541512, 541513, 541511, 561210]
      keywords: [data center, virtualization, cloud, IaC, network architecture, storage, disaster recovery, Kubernetes, SEWP, ITES]
      set_asides: [SDVOSBC, SDVOSBS, VSA, VSS, SBA, SBP, SB]
    alert_threshold: 70
  - name: Brian — Quality daily
    owner_slug: brian-macdonald
    filters:
      naics: [541380, 541614, 541611, 541618]
      keywords: [ISO 9001, ISO 17025, metrology, calibration, audit, QMS, accreditation, laboratory]
    alert_threshold: 65   # lower threshold — narrower funnel
  - name: John — Governance weekly
    owner_slug: john-milso
    filters:
      naics: [541110, 541199, 541611, 541618]
      keywords: [legal services, contract review, compliance, risk advisory, corporate governance]
    alert_threshold: 60
    alert_cadence: weekly

mactech_capabilities_seed:
  - title: CMMC 2.0 Level 2 Implementation & Assessment Readiness
    related_naics: [541519, 541512, 541611]
    related_founders: [patrick-caruso, brian-macdonald]
  - title: DoD RMF / ATO Package Development
    related_naics: [541519, 541512]
    related_founders: [patrick-caruso]
  - title: Continuous Monitoring (ConMon) Program Design
    related_naics: [541519, 541513]
    related_founders: [patrick-caruso]
  - title: Data Center Architecture & Cloud Migration
    related_naics: [518210, 541330, 541512, 541513]
    related_founders: [james-adams]
  - title: Infrastructure as Code & DevSecOps
    related_naics: [541511, 541512, 541330]
    related_founders: [james-adams]
  - title: ISO 17025 Metrology & Calibration Program Management
    related_naics: [541380]
    related_founders: [brian-macdonald]
  - title: ISO 9001 Quality Management System Implementation
    related_naics: [541611, 541614]
    related_founders: [brian-macdonald]
  - title: Federal Contract Review & Teaming Agreement Counsel
    related_naics: [541110, 541199]
    related_founders: [john-milso]
  - title: Risk Advisory & Compliance Governance
    related_naics: [541611, 541618]
    related_founders: [john-milso]
```

**Brian / Patrick: fill in the UEI and CAGE code when registration is complete. Everything else is ready.**

---

## 9. Exclusions & compliance gates — the non-negotiable guardrails

Because MacTech is a new SDVOSB with licensed legal counsel in-house (John), we can afford to be *more* rigorous than typical small businesses, not less. This is a differentiator when bidding.

### Gate 1 — Stage "Pursue" requires incumbent screened

Before a pursuit advances to "Pursue," the incumbent (from USASpending lookup) must have:
- Exclusions check run in last 24 hours
- Been researched (basic entity record populated)

Gate action: block stage change with a one-click "Run checks now" button.

### Gate 2 — Stage "Submit" requires full team clean

Before a pursuit advances to "Submit":
- MacTech's own UEI: exclusions check clean
- Every teaming partner: exclusions check clean
- Every key personnel (named in proposal): not on exclusions list
- John (governance) has marked the pursuit "Legal review complete"

Gate action: block with checklist showing which items are incomplete.

### Gate 3 — SDVOSB certification-pending warning

Until MacTech's SDVOSB certification is formal, any pursuit of an SDVOSB set-aside opportunity displays a yellow banner: *"SDVOSB certification is pending. Confirm eligibility with the contracting officer before submission."*

---

## 10. MacTech's internal analytics — what we measure

Insights screen has four panels. All MacTech-specific.

### Panel 1 — Capture funnel
- Opportunities scored above threshold (last 30 / 90 / 365 days)
- % moved to Qualify
- % moved to Pursue
- % moved to Propose
- % moved to Submit
- Win rate on submitted
- Trailing 90-day win rate trend

### Panel 2 — Pillar productivity
For each founder:
- Opportunities they own (by stage)
- Their personal win rate
- Avg cycle time (Lead → Submit)
- # of Sources Sought responses drafted
- # of capability statements they're named on

### Panel 3 — NAICS performance
- Wins per NAICS code
- Pipeline value per NAICS
- Which of our 20 codes are *actually* generating pursuits (may surprise us)
- Which primary codes are under-performing and may need to de-prioritize

### Panel 4 — Agency penetration
- Agencies we've submitted to
- Agencies we've won from
- Agencies where we have open pursuits but no wins yet (= investment areas)
- Agencies on our target list with zero activity (= capture effort gaps)

These metrics feed the quarterly MacTech capture review. Year 1 target on Panel 1: submit ≥ 12 proposals, win ≥ 2. Year 1 target on Panel 3: at least 6 of our 20 NAICS have produced a pursuit.

---

## 11. Phase 1 scope clarifications — what "done" looks like for MacTech

Given the MacTech-first framing, some Phase 1 priorities shift. Updating the Week-by-Week:

| Week | Original (SaaS-generic) | MacTech-first adjustment |
|---|---|---|
| 1 | Infra skeleton | Same + seed MacTech tenant defaults from `config/mactech_tenant_defaults.yml` |
| 2 | SAM.gov ingest | Same, but the test harness runs *MacTech's real NAICS + set-aside filters* |
| 3 | Enrichment + embeddings | Same |
| 4 | Scoring + morning digest | **Ship this with the 4 real digests** to Brian@, Patrick@, James@, John@ — not a generic demo account |

End of Phase 1, success criterion:

> At 6am ET on a Tuesday, all four MacTech founders receive a real email listing 3–5 real, scored, recently-posted opportunities they should actually consider pursuing — with accurate incumbent info, relevant capability statement matches, and a "Why this matters" paragraph written by Claude that reads like it was written by a GovCon strategist, not by a chatbot.

That's the bar. If the Tuesday email is good, Phase 1 succeeded. If not, we fix what's wrong before Phase 2 starts.

---

## 12. The "found out about this tool too late" test

Every feature proposal gets this test: *If MacTech had this feature 90 days earlier, would it have changed an outcome?*

- Sources Sought response drafter → yes (MacTech misses Sources Sought all the time, and Sources Sought responses shape requirements)
- Compliance matrix auto-generator → yes (20 hours of manual shredding eliminated per proposal)
- Teaming partner marketplace → maybe (valuable but not as urgent when MacTech is still finding its first few wins)
- White-label reseller portal → no (Year 2 problem)

Build the yeses first. Park the no's. Sprint through the maybes last.
