# Data Sources — MacTech CaptureOS

Full reference for every external API and scrape target, with auth, rate limits, schemas, and implementation notes. Every integration lives in `packages/integrations/<source_name>/`.

## Legend

- **Tier 1** — Free, stable, public APIs. Build against these Week 1.
- **Tier 2** — Scraping required (via Apify).
- **Tier 3** — Web augmentation (SerpAPI).
- **Tier 4** — AI providers.
- **Tier 5** — Paid intelligence (Year 2+ consideration).

---

## Tier 1 — Core federal APIs

### 1.1 SAM.gov Get Opportunities API

**Purpose:** Primary opportunity feed. Sources Sought, Presolicitations, Combined Synopsis/Solicitations, Solicitations, Sale of Surplus Property, Award Notices.

**Base URL:** `https://api.sam.gov/opportunities/v2/search`

**Auth:** API key via header `X-Api-Key: <key>` or query param `api_key=<key>`. Register at https://sam.gov → Profile → Account Details → Request API Key.

**Rate limit:** 1,000 requests / hour with API key. 10 requests / day without.

**Key parameters:**
- `postedFrom` / `postedTo` — MM/dd/yyyy
- `ncode` — NAICS code (we use our 20-code matrix)
- `typeOfSetAside` — SDVOSBC (SDVOSB Set-Aside), SDVOSBS (Sole Source), etc.
- `deptname`, `orgKey` — filter by agency
- `responseDeadLineFrom` / `responseDeadLineTo` — deadline filters
- `limit` (max 1000), `offset`

**Implementation notes:**
- Schedule: every 2 hours business days, every 6 hours off-hours
- Incremental fetch using `postedFrom = last_successful_run`
- Upsert on `noticeId` (primary key in our raw table)
- Store the full response JSON in a `raw_payload` jsonb column — the API schema changes occasionally

**Docs:** https://open.gsa.gov/api/get-opportunities-public-api/

### 1.2 SAM.gov Entity Management API

**Purpose:** Verify entity registrations, competitor intel, set-aside eligibility lookups.

**Base URL:** `https://api.sam.gov/entity-information/v3/entities`

**Auth:** Same API key as Opportunities API. Note: only "public data" is accessible without FOUO certification.

**Rate limit:** 1,000 / hour.

**Key parameters:**
- `ueiSAM` — UEI (Unique Entity ID)
- `cageCode`
- `legalBusinessName`
- `registrationStatus` — "A" = Active, "E" = Expired

**Implementation notes:**
- Used for three flows: (a) on opportunity ingest, look up the soliciting office; (b) on pursuit setup, verify teaming partners; (c) on competitor research, pull peer set
- Cache 7 days — entity data changes infrequently

**Docs:** https://open.gsa.gov/api/entity-api/

### 1.3 SAM.gov Exclusions API

**Purpose:** Debarment and suspension list. Mandatory check — submitting a proposal that includes an excluded entity is disqualifying.

**Base URL:** `https://api.sam.gov/entity-information/v4/exclusions`

**Auth:** Same API key.

**Rate limit:** 1,000 / hour.

**Implementation notes:**
- Run a screening on every pursuit before "Submit" stage
- Screen the prime, all subcontractors, and all key personnel
- Block pursuit advancement if any match is found; require human override with documented reason
- Cache 24 hours

**Docs:** https://open.gsa.gov/api/exclusions-public/

### 1.4 USASpending.gov API

**Purpose:** Historical contract awards. Incumbent detection, ceiling analysis, competitor wins.

**Base URL:** `https://api.usaspending.gov/api/v2/`

**Auth:** None. Public API.

**Rate limit:** Published as "reasonable use." In practice, throttle to 1 req/sec.

**Key endpoints:**
- `POST /search/spending_by_award/` — search awards by agency, NAICS, recipient, date range
- `GET /awards/{award_id}/` — full award detail
- `POST /recipient/duns/` — recipient profile by UEI
- `POST /search/spending_by_transaction/` — transaction-level detail

**Implementation notes:**
- Key use case: "who is the incumbent on this recompete?" — search awards where `naics_code` + `awarding_agency` match, `period_of_performance_current_end_date` falls within 24 months of the new opportunity's posted date
- Bulk ingest quarterly awards snapshot for our target agencies into `awards_history` table

**Docs:** https://api.usaspending.gov/

### 1.5 FPDS-NG Atom Feed

**Purpose:** Near-real-time contract action stream. Faster than USASpending for fresh awards.

**Base URL:** `https://www.fpds.gov/ezsearch/fpdsportion/fpdsportion?feedname=PUBLIC&indexName=awardfull&templateName=PUBLIC&q=`

**Auth:** None.

**Format:** ATOM XML feed.

**Key parameters (appended to `q`):**
- `PIID:...` — procurement instrument identifier
- `CONTRACTING_AGENCY_ID:...`
- `PRINCIPAL_NAICS_CODE:...`
- `SIGNED_DATE:[2026/01/01,2026/12/31]`

**Implementation notes:**
- Poll every 4 hours for our target NAICS codes
- Parse XML → normalize into `awards_history` table alongside USASpending data
- Deduplicate on PIID

**Docs:** https://www.fpds.gov/wiki/index.php/FPDS-NG

### 1.6 SBA Dynamic Small Business Search (DSBS)

**Purpose:** Verify small business, SDVOSB, 8(a), HUBZone, WOSB status of competitors and potential teaming partners.

**Base URL:** `https://api.sba.gov/...` (DSBS public data)

**Auth:** None for basic queries.

**Implementation notes:**
- Used at pursuit-setup time to verify a teaming partner's small-business claims
- Cached 30 days — certifications change infrequently but do change

**Docs:** https://api.sba.gov/

---

## Tier 2 — Scraping via Apify

Apify is our scraping infrastructure. Use existing actors where possible; build custom actors only when nothing public fits.

**Apify auth:** API token in `APIFY_API_TOKEN` env var. Client library: `apify-client` Python package.

### 2.1 Agency forecast pages

**Targets:**
- DoD forecasts (many — start with DoD OSBP)
- DHS, VA, DOE, DOT forecast portals
- GSA forecast system
- Air Force, Army, Navy small business forecasts

**Strategy:**
- One custom Apify actor per agency (agency pages are templated but not uniform)
- Run weekly
- Normalize into `agency_forecasts` table with fields: agency, office, description, estimated_value, estimated_solicitation_date, estimated_award_date, naics_code, set_aside

**Priority:** Target MacTech's top 3 agencies first — Navy, DISA, VA.

### 2.2 DIBBS (DLA Internet Bid Board System)

**URL:** https://www.dibbs.bsm.dla.mil/

**Strategy:**
- Apify actor scraping Open Solicitations page
- DoD supply opportunities (largely FedMall-adjacent)
- Relevant if MacTech pursues supply/hardware angles

**Priority:** Phase 2.

### 2.3 GSA eBuy

**URL:** https://www.ebuy.gsa.gov/

**Access:** GSA Schedule holder login required. Once MacTech is on a GSA Schedule, we can scrape logged-in views.

**Priority:** Phase 2+ (after MacTech is on-Schedule).

### 2.4 FedConnect

**URL:** https://www.fedconnect.net/

**Purpose:** DOE, DLA, some civilian agency solicitations not on SAM.

**Priority:** Phase 2.

---

## Tier 3 — Web augmentation via SerpAPI

**Auth:** API key in `SERPAPI_KEY`. Python client: `google-search-results`.

**Rate limit:** Based on plan. Start at Developer plan (~$75/mo, 5k searches).

**Use cases:**

1. **Agency industry day discovery.** Query: `"<agency> industry day <current quarter>"` → parse announcements from agency / trade press sites.
2. **Contracting officer lookup.** Query: `"<agency name> contracting officer site:linkedin.com"` → for proactive relationship building (human-delivered, not automated outreach).
3. **Incumbent competitive news.** Periodic queries like `"<incumbent company> contract <agency>"` to catch financial news, layoffs, acquisitions that weaken their recompete position.
4. **MacTech mentions / brand monitoring.** Standard SEO hygiene.

**Implementation notes:**
- Cache results 7 days — paid queries are expensive
- Strict rate limit awareness
- Never use SerpAPI results for automated outbound; human-reviewed only

---

## Tier 4 — AI providers

### 4.1 Anthropic Claude API

**Base URL:** `https://api.anthropic.com/v1/messages`

**Auth:** API key `ANTHROPIC_API_KEY`.

**Models used:**
- `claude-sonnet-4-6` — complex drafting (Sources Sought responses, compliance matrices, proposal shred-outs)
- `claude-haiku-4-5-20251001` — high-volume classification and scoring
- `claude-opus-4-7` — when deep reasoning genuinely warrants the cost (rare; capture strategy deep-dives)

**Patterns:**
- Structured outputs via tool use / JSON mode
- System prompts live in `packages/intelligence/prompts/` with version tags
- All calls logged (request hash + response) for audit and replay

### 4.2 Voyage Embeddings

**Purpose:** Semantic search across opportunities and capability statements.

**Model:** `voyage-3` (1024-dim) or `voyage-3-large` (1536-dim if budget allows).

**Auth:** `VOYAGE_API_KEY`.

**Usage:**
- Embed every opportunity description on ingest
- Embed every MacTech capability statement + past performance entry on create/update
- Nearest-neighbor query via pgvector `<=>` operator for "find capability statements similar to this opportunity"

### 4.3 OpenAI (backup)

Abstract behind `LLMClient` interface. Fallback when Anthropic is down or when cost arbitrage makes sense.

**Models:** `gpt-4o`, `gpt-4o-mini`, `text-embedding-3-large`.

---

## Tier 5 — Paid intelligence (Year 2+ evaluation)

Not integrated in MVP. Listed for future planning.

| Source | Annual cost | What it adds | Priority |
|---|---|---|---|
| HigherGov API | $6k–$24k | Cleaner opportunity data, agency contacts, contract vehicle metadata | High — evaluate Month 9 |
| Deltek GovWin IQ API | $15k–$40k | Deepest pipeline intelligence, forecasts, agency spending plans | Medium — evaluate Year 2 |
| Bloomberg Government | $6k–$15k | Policy / legislative intel, editorial analysis | Low — evaluate Year 2 |
| FedMine | $3k–$8k | Contract history depth | Low |

---

## Data normalization targets

Every external source flows into a normalized internal schema. See `docs/SCHEMA.md` for the full schema. Key tables:

- `opportunities_raw` — one row per external opportunity, keyed by source + source_id
- `opportunities_enriched` — derived fields (incumbent, scored NAICS match, set-aside eligibility, parsed requirements)
- `awards_history` — merged USASpending + FPDS award records
- `entities` — normalized contractor/agency records from SAM Entity API + SBA DSBS
- `agency_forecasts` — from Apify scrapes
- `external_signals` — from SerpAPI (industry days, news items)

---

## Environment variables reference

```bash
# Required for MVP
SAM_API_KEY=...                    # sam.gov account → request key
APIFY_API_TOKEN=...                # console.apify.com
SERPAPI_KEY=...                    # serpapi.com
ANTHROPIC_API_KEY=...              # console.anthropic.com
VOYAGE_API_KEY=...                 # voyage.ai

# Optional / backup
OPENAI_API_KEY=...

# Infra
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mactech
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000  # MinIO dev
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=mactech-documents

# Auth
CLERK_PUBLISHABLE_KEY=...
CLERK_SECRET_KEY=...
CLERK_JWT_KEY=...

# Observability
SENTRY_DSN=...
POSTHOG_API_KEY=...
```

---

## Rate-limit summary table

| Source | Limit | Our plan |
|---|---|---|
| SAM.gov Opps | 1,000/hr | 2-hour incremental pulls, ≤ 20 calls each |
| SAM.gov Entity | 1,000/hr | On-demand, cached 7 days |
| SAM.gov Exclusions | 1,000/hr | On-demand at pursuit submit, cached 24h |
| USASpending | ~1 req/sec soft | Throttled client, 1 req/sec |
| FPDS Atom | None published | 4-hour polls |
| Apify | Plan-dependent | Scheduled runs, not real-time |
| SerpAPI | Plan-dependent | Cached 7 days, human-triggered mostly |
| Anthropic | Tier-based | Cache aggressively; batch where possible |
| Voyage | Plan-based | One embedding per opportunity, one per capability |
