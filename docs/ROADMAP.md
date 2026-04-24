# Roadmap — MacTech CaptureOS

90-day MVP plan. Every week ships something demoable. Friday = review + PROGRESS.md update.

---

## Phase 1 — Foundation & SAM.gov ingest (Weeks 1–4)

**Goal:** Daily SAM.gov opportunity ingestion running, MacTech team receiving morning digests of scored opportunities.

### Week 1 — Infrastructure skeleton

- [ ] Repo init (monorepo layout per ARCHITECTURE.md §2)
- [ ] `docker-compose.yml` with Postgres 16 + pgvector, Redis 7, MinIO, MailHog
- [ ] `uv`-based Python workspace; pnpm workspace for JS
- [ ] `.env.example` with every variable documented
- [ ] Alembic init + `tenants`, `users`, `founders`, `naics_codes`, `founder_naics_matrix` migrations
- [ ] Seed script for MacTech tenant + 4 founders + NAICS matrix from `data/*.json`
- [ ] GitHub Actions: lint (ruff, eslint), type check (mypy, tsc), test
- [ ] Sentry wiring, structured logging baseline

**Demo at Friday review:** `docker compose up` produces a healthy stack; `pnpm seed` loads MacTech's founders and NAICS matrix visible via `psql`.

### Week 2 — SAM.gov Opportunities ingestion

- [ ] `packages/integrations/sam_gov/` — typed client with rate-limited wrapper (aiohttp + asyncio-throttle)
- [ ] Pydantic models for SAM.gov Opportunities response
- [ ] `opportunities_raw` migration, including embedding column
- [ ] Celery worker + Beat: `ingest_sam_opportunities` every 2h during business hours
- [ ] Upsert logic keyed by `noticeId`; store full `raw_payload`
- [ ] Integration tests with mocked SAM responses
- [ ] Manual backfill: pull last 30 days of opportunities matching MacTech's 20 NAICS codes

**Demo:** Fresh Postgres DB populated with ~1,000+ real opportunities. Query them by NAICS, agency, date.

### Week 3 — Enrichment & embeddings

- [ ] `packages/integrations/usaspending/` client
- [ ] `packages/integrations/voyage/` embeddings client
- [ ] `awards_history` table + ingest worker pulling USASpending for MacTech's top 5 agencies
- [ ] `enrich_opportunity` worker:
  - [ ] Compute Voyage embedding on description
  - [ ] Incumbent detection: find most recent award with matching NAICS + agency
  - [ ] Exclusions check (SAM.gov Exclusions API) on incumbent
- [ ] `opportunities_enriched` populated
- [ ] Exclusion screening cached in `exclusions_cache`

**Demo:** For any opportunity, `GET /opportunities/{id}/enriched` returns incumbent name, their award history, and an exclusions-clear signal.

### Week 4 — Scoring + morning digest

- [ ] `packages/intelligence/scoring.py` implementing the weighted-sum scorer
- [ ] `opportunity_scores` populated per tenant
- [ ] `why_it_matters` paragraph generated via Claude Sonnet (Anthropic client in `packages/integrations/anthropic/`)
- [ ] `saved_searches` table + default saved search per founder based on their NAICS
- [ ] Morning digest email job (Celery Beat, 7am ET weekdays): top 5 opportunities for each founder
- [ ] Email template (MJML or react-email)

**Demo:** Each founder receives a real 7am email listing 3–5 scored opportunities with rationale. **Phase 1 complete.**

---

## Phase 2 — Pipeline & intelligence (Weeks 5–8)

**Goal:** MacTech team can run their capture pipeline in the app. Opportunities → pursuits → decisions tracked.

### Week 5 — Web app shell + auth

- [ ] Next.js 14 app scaffold with App Router
- [ ] Clerk auth wired; tenant context propagated via JWT claim
- [ ] API layer: FastAPI with Clerk JWT verification, tenant context middleware
- [ ] RLS policies activated on tenant-scoped tables
- [ ] Layout: sidebar (Dashboard, Opportunities, Pipeline, Library, Settings), top nav, user menu
- [ ] Empty dashboard page with KPI shells

**Demo:** Four founders log in; each sees MacTech's data only.

### Week 6 — Opportunity feed UI

- [ ] `/opportunities` page: list view with filters (NAICS, agency, set-aside, value, score threshold)
- [ ] `/opportunities/[id]` detail view: full raw data + enrichment + score breakdown + incumbent card + "Why this matters" paragraph
- [ ] Saved search management UI
- [ ] Real-time search with trgm similarity on title/description
- [ ] Export to CSV

**Demo:** Patrick filters for NAICS 541519 + SDVOSB set-aside and pulls up the current week's top opportunities.

### Week 7 — Capture pipeline kanban

- [ ] `pursuits` + `pursuit_events` tables
- [ ] Pipeline UI: kanban columns (Lead → Qualify → Pursue → Propose → Submit → Won/Lost)
- [ ] Drag-to-move with event logging
- [ ] Pursuit detail page: opportunity link, owner assignment, bid/no-bid field, PWIN, deadline countdown, notes, activity feed
- [ ] Auto-suggest founder assignment based on `founder_naics_matrix`
- [ ] "Add to pipeline" button from opportunity detail

**Demo:** MacTech moves 3 real opportunities into the pipeline, assigns owners, logs bid/no-bid decisions.

### Week 8 — Capability library + teaming

- [ ] `capability_statements` + `past_performance` tables
- [ ] CRUD UI for both
- [ ] Auto-embed on create/update
- [ ] On a pursuit page, show "Matching capability statements" via pgvector similarity
- [ ] `teaming_partners` table + basic CRUD

**Demo:** On opening a pursuit, Claude-generated suggestion of which 2–3 capability statements are most relevant. **Phase 2 complete.**

---

## Phase 3 — AI automation (Weeks 9–12)

**Goal:** Sources Sought drafting, compliance matrix generation, document parsing. The differentiators.

### Week 9 — Document upload + parsing

- [ ] `documents` table
- [ ] S3/MinIO upload flow
- [ ] Multi-format text extraction: PDF (pdfplumber), DOCX (python-docx), TXT, HTML
- [ ] Background parse worker populates `documents.parsed_content`
- [ ] Pursuit detail: "Attach solicitation" → shows parsed text preview

**Demo:** Upload a real solicitation PDF; its text is extracted and viewable within 30 seconds.

### Week 10 — Compliance matrix generator

- [ ] Prompt template in `packages/intelligence/prompts/compliance_matrix.md`
- [ ] Claude Sonnet call parses Section L (instructions) + Section M (evaluation) into structured requirements
- [ ] `compliance_matrices` table populated with requirement rows
- [ ] Matrix UI: table view, assign owner, mark status (not started / in progress / complete)
- [ ] Export to Excel

**Demo:** Solicitation upload → 90 seconds later a draft compliance matrix with 30–60 requirements ready for review.

### Week 11 — Sources Sought auto-drafter

- [ ] Prompt template consuming: opportunity raw → matched capability statements → past performance → founder bios
- [ ] Claude Sonnet generates a Sources Sought response draft
- [ ] In-app editor (TipTap or Lexical) for human refinement
- [ ] Save as `documents` record linked to pursuit

**Demo:** Click "Draft Sources Sought response" on a real Sources Sought opportunity; 45 seconds later a 2–3 page draft is editable in the browser.

### Week 12 — Polish, analytics, internal launch

- [ ] Dashboard KPIs: # opportunities this week, # in pipeline, # proposals out, $ potential pipeline value, win rate
- [ ] PostHog event instrumentation on every meaningful user action
- [ ] Critical error handling pass; test disaster scenarios (DB outage, API down, LLM down)
- [ ] Internal announcement and training for the 4 founders
- [ ] Baseline metrics captured for "before vs after" comparison

**Demo / review:** Full end-to-end: new opportunity arrives overnight → scored → morning email → founder reviews → moves to Qualify → drafts Sources Sought → submits. **Phase 3 complete. MVP done.**

---

## Phase 4 — External beta (Months 4–6, post-MVP)

- [ ] Marketing site + pricing page
- [ ] Stripe billing integration
- [ ] Onboarding wizard for external tenants
- [ ] Invite 10 SDVOSB cohort members (outside MacTech's NAICS footprint)
- [ ] Weekly office hours with cohort
- [ ] Convert ≥3 to paid ($299/mo) by end of Month 6
- [ ] First "Done-With-You" managed capture engagement closed and delivered ($15k+)

## Phase 5 — CMMC Readiness Engine (Months 7–9)

- [ ] NIST 800-171 R3 control catalog imported
- [ ] Self-assessment workflow
- [ ] Evidence upload + metadata tagging
- [ ] POA&M generator
- [ ] Auto-export audit bundle (PDF + evidence archive)
- [ ] Price: $5k–$25k engagement

## Phase 6 — Intelligence data products (Months 10–12 / Year 2)

- [ ] Data products team charter
- [ ] First report: "DIB Recompete Forecast Q3 2026" — priced at $1,500
- [ ] Newsletter subscription: $199/mo
- [ ] API access for large primes (rate-limited, read-only)

---

## Tracking & ritual

- `docs/PROGRESS.md` updated at end of every work session (Claude Code writes this)
- Friday review with all 4 founders: what shipped, what slipped, what's blocking
- Every shipped feature gets a 2-line changelog entry
- Every new metric viewable from the dashboard
