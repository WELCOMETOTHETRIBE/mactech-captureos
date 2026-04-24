# CLAUDE.md — MacTech CaptureOS Project Context

**This file is your always-on operating context. Read it on every new session before you touch code.**

---

## 1. Who we are

**MacTech Solutions LLC** — Veteran-owned consulting firm (SDVOSB pending), specializing in DoD cybersecurity, infrastructure engineering, and compliance for federal programs and defense contractors.

Web: https://www.mactechsolutionsllc.com

**Four founding members (all key personnel, all available for proposals):**

- **Brian MacDonald** — Managing Member, Compliance & Operations. Pillar: **Quality**. ISO 9001/17025, audit readiness, metrology, process documentation.
- **Patrick Caruso** — Director of Cyber Assurance. Pillar: **Security**. RMF, ATO, ConMon, STIG, CMMC 2.0 L2, NIST CSF 2.0, FedRAMP Moderate.
- **James Adams** — Director of Infrastructure & Systems Engineering. Pillar: **Infrastructure**. Data center architecture, virtualization, cloud, storage, network, IaC.
- **John Milso** — Director of Legal, Contracts & Risk Advisory. Pillar: **Governance**. Former Senior Legal Counsel at a global public software company. Licensed in MA + RI. Commercial contracts, corporate governance, M&A diligence, risk.

Structured founder records: `data/founders.json`
NAICS-to-founder mapping: `data/naics_matrix.json`

---

## 2. What we're building

**Product name:** MacTech CaptureOS
**Tagline:** The operating system for defense contractors.
**One-liner:** Identify, win, and stay eligible for federal work — capture intelligence, proposal automation, and CMMC readiness in one platform built by the team that uses it to win contracts themselves.

**Phase 1 reality:** This product is first and foremost MacTech's internal capture weapon. Every API call, every dashboard panel, every scheduled job in Phase 1 exists because it helps the 4 founders identify and win their next federal contract. External SaaS is Phase 4+ scaffolding that exists in the architecture but is not built, marketed, or sold yet.

**Phase 1's governing spec is `docs/MACTECH_PLAYBOOK.md` — read it.** It defines what each founder needs from the product, MacTech's NAICS and set-aside profile, the target agencies, the specific integration calls, the dashboard layout, and the scoring configuration. When `PRD.md` says something generic and `MACTECH_PLAYBOOK.md` says something MacTech-specific, the playbook wins for Phase 1.

**Phase 1 seed configuration:** `config/mactech_tenant_defaults.yml` — Claude Code reads this in Week 1 to seed the MacTech tenant with real NAICS codes, saved searches per founder, capability statements, and scoring weights.

**Not:** "a compliance tool" or "a SAM.gov scraper" or "a BD dashboard." Reject any framing that reduces the product to one of those.

**Four revenue lines, sequenced by cash velocity:**

1. **Managed Capture + CMMC services** (month 1, services first — funds the build)
2. **CaptureOS SaaS** (month 6 — $199 / $599 / $1,499 / enterprise tiers)
3. **CMMC Readiness Engine** (month 9 — $5k–$25k engagement + monitoring retainer)
4. **Intelligence Data Products** (year 2 — reports + newsletter)

**Revenue Line Zero:** MacTech's own contract wins. The platform is first and foremost MacTech's internal BD engine. Every feature must earn its place by either (a) helping MacTech win a contract or (b) being something a DIB customer would pay for. If it's neither, we don't build it.

See `docs/POSITIONING.md` for the full business frame.
See `docs/PRD.md` for product requirements.

---

## 3. Core principles (non-negotiable)

1. **CMMC 2.0 Level 2 alignment from day one.** Our customers are DIB contractors handling CUI. We cannot retrofit CUI handling later. Every architectural decision considers CUI boundaries, access control, audit logging, and data residency.
2. **Multi-tenant with hard isolation.** A customer's opportunities, pursuits, capability data, and documents MUST NOT leak across tenants. Design with row-level security (RLS) in PostgreSQL and tenant-scoped queries enforced at the ORM layer, not just the UI.
3. **Veteran-owned voice.** Copy, UI, error messages — sober, plainspoken, competent. No marketing hype. No emoji in product UI. We are selling to COs, KOs, CISOs, and BD leads who hate fluff.
4. **Data sources are public but the intelligence layer is the moat.** Scraping and API integration is table stakes — AI scoring, incumbent intel, auto-generated compliance matrices, and workflow are what we sell.
5. **Ship weekly.** MVP in 90 days. If a task hasn't produced a shippable increment in 5 business days, it's too big — decompose it.

---

## 4. Architecture at a glance

**Full details in `docs/ARCHITECTURE.md` and `docs/AGENT_ARCHITECTURE.md`.** Quick summary:

- **Backend:** Python 3.12 + FastAPI, async-first
- **DB:** PostgreSQL 16 with pgvector extension for semantic search
- **Cache / queue:** Redis 7 + Celery (or RQ) for scheduled ingestion
- **Storage:** S3-compatible (start with local MinIO for dev, move to AWS S3 or Cloudflare R2 for prod; eventually AWS GovCloud S3 once revenue justifies)
- **Frontend:** Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
- **Auth:** Clerk (fast to ship) with SAML SSO for enterprise tier later
- **AI:** Claude Agent SDK (primary, subscription-powered for internal work — see `docs/AGENT_ARCHITECTURE.md`), Anthropic commercial API + BYO-key for external customers, Voyage embeddings, OpenAI as backup
- **Search:** PostgreSQL full-text + pgvector (no Elasticsearch unless we hit scale ceiling)
- **Infra:** Docker for dev; Fly.io or Railway for early prod; GovCloud migration planned for Year 2
- **Observability:** Sentry + PostHog + Better Stack

**Repo layout:**

```
mactech-captureos/
├── apps/
│   ├── api/              # FastAPI backend
│   ├── web/              # Next.js frontend
│   └── workers/          # Celery workers for ingestion
├── packages/
│   ├── db/               # Shared DB migrations, SQLAlchemy models
│   ├── integrations/     # SAM.gov, USASpending, Apify, SerpAPI, Anthropic clients
│   └── intelligence/     # Scoring, matching, parsing, compliance logic
├── docs/                 # You're reading these
├── data/                 # Seed data (founders, NAICS)
└── infra/                # Docker, docker-compose, deploy configs
```

---

## 5. Data sources you will integrate

**Full reference in `docs/DATA_SOURCES.md`.** High-level:

| Tier | Source | Purpose | Auth |
|---|---|---|---|
| 1 | SAM.gov Get Opportunities API | Core opportunity feed | API key |
| 1 | SAM.gov Entity Management API | Competitor / teaming intel | API key |
| 1 | SAM.gov Exclusions API | Debarment screening (mandatory) | API key |
| 1 | USASpending.gov API | Historical awards, incumbent detection | None |
| 1 | FPDS-NG Atom Feed | Near-real-time award stream | None |
| 1 | SBA DSBS API | Small business / SDVOSB verification | None |
| 2 | Apify | Scrape agency forecast pages, DIBBS, FedConnect | API token |
| 2 | SerpAPI | Web augmentation, LinkedIn CO intel | API key |
| 3 | Grants.gov API | Grants pipeline (Year 2) | None |
| 3 | GSA CALC API | Labor rate intelligence | None |
| 4 | Claude Agent SDK | Primary AI layer — subscription-powered for MacTech | `claude login` |
| 4 | Anthropic commercial API | External customer billing path | API key |
| 4 | Voyage embeddings | Opportunity-capability semantic match | API key |

**Rate-limit aware from day one.** Every external client goes through a rate-limited wrapper with exponential backoff. Never hammer an API.

**Idempotency.** Every ingestion run must be safely re-runnable. Use upserts keyed by the source's unique ID (noticeId for SAM.gov, award_id for USASpending, etc.).

---

## 6. The NAICS matrix (MacTech's registered codes)

**Structured data:** `data/naics_matrix.json`
**Spreadsheet:** `data/MacTech_NAICS_Matrix.xlsx`

**Primary codes (8):** 541519, 541512, 518210, 541513, 541611, 541330, 541380, 541110
**Secondary codes (12):** 541618, 541511, 541614, 611420, 611430, 541199, 561621, 561210, 541715, 541690, 541990, 611710

The scoring engine must boost opportunities matching primary codes over secondary codes. Founder-to-NAICS mapping drives automatic pursuit routing — when an opportunity with NAICS 541380 is scored, Brian is auto-assigned; 541110 routes to John; etc.

---

## 7. How to work with me (operating agreement)

**When you start a session:**
1. Read this file.
2. Read `docs/ROADMAP.md` and find the current phase.
3. Check the repo for work-in-progress (open PRs, unfinished branches, TODOs).
4. Confirm with the user what they want to work on. If they say "keep going," proceed with the next open roadmap task.

**While working:**
- Ask clarifying questions early rather than assuming. Better to pause 30 seconds than rebuild an afternoon.
- Write tests. Aim for ≥70% coverage on business logic (scoring, ingestion, compliance matrix).
- Prefer small, reviewable commits over sweeping refactors.
- When you hit a decision point with tradeoffs (e.g., Celery vs RQ, Clerk vs Auth.js), surface it briefly with a recommendation — don't just pick silently.
- Treat `data/founders.json` and `data/naics_matrix.json` as source of truth, not the xlsx.

**What not to do:**
- Don't invent API endpoints. If the SAM.gov docs don't describe a field, ask before assuming.
- Don't scaffold huge unused modules. YAGNI.
- Don't add dependencies without explaining the tradeoff.
- Don't put production secrets in code. `.env.example` only.
- Don't write marketing copy in the product. That's a human task.

**Progress reporting:**
At the end of every working session, update `docs/PROGRESS.md` with: what shipped, what's half-done, what's blocked, what's next.

---

## 8. The user you're talking to

The four founders are senior technical practitioners but not full-stack SaaS builders. Patrick and James read code fluently; Brian and John are less code-oriented. When explaining technical choices, write for the level that all four can follow. Avoid jargon that isn't GovCon-native or standard enough that anyone in tech would recognize it.

---

## 9. First task (if the user hasn't specified)

Default to: "Read `docs/MACTECH_PLAYBOOK.md` and `config/mactech_tenant_defaults.yml` in full. Then set up the monorepo skeleton per section 4, wire up `docker-compose` for local Postgres + Redis + MinIO, scaffold the Phase 1 Week 1 seed migration that loads the MacTech tenant from the config YAML, and stub the SAM.gov Opportunities ingestion worker. Target: `docker compose up` produces a healthy stack with MacTech tenant + 4 founders + 20 NAICS codes + 4 saved searches already seeded. See `docs/ROADMAP.md` Phase 1 Week 1-2."

Confirm with the user before proceeding.
