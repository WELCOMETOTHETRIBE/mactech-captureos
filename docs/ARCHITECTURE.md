# Architecture — MacTech CaptureOS

## 1. System overview

Four logical tiers:

1. **Ingestion** — Scheduled workers pull from public APIs + scrape gated sources; results land in a normalized PostgreSQL schema.
2. **Intelligence** — Scoring, incumbent detection, document parsing, compliance matrix generation. Mix of deterministic rules and LLM calls.
3. **Workflow** — Capture pipeline (kanban), pursuit records, capability library, proposal drafts.
4. **Presentation** — Next.js frontend + FastAPI surface; notifications (email/SMS/Slack).

```
┌────────────────────────────────────────────────────────────────┐
│ Next.js 14 Web App (apps/web)                                  │
│   • Dashboard • Pipeline • Opportunity detail • Settings       │
└────────────────────────────────────────────────────────────────┘
                            ▲ HTTPS
                            │
┌────────────────────────────────────────────────────────────────┐
│ FastAPI API (apps/api)                                         │
│   • Auth (Clerk JWT) • Tenant scoping • CRUD • AI endpoints    │
└────────────────────────────────────────────────────────────────┘
     │                  │                  │                │
     ▼                  ▼                  ▼                ▼
┌──────────┐      ┌──────────┐      ┌──────────────┐   ┌──────────┐
│PostgreSQL│      │  Redis   │      │   S3/MinIO   │   │Claude API│
│+pgvector │      │(cache,q) │      │ (documents)  │   │          │
└──────────┘      └──────────┘      └──────────────┘   └──────────┘
     ▲                  ▲
     │                  │
┌────────────────────────────────────────────────────────────────┐
│ Celery Workers (apps/workers)                                  │
│   • SAM.gov ingest • USASpending ingest • Scoring • Embeddings │
│   • Apify scrape • Doc parse • Compliance matrix build         │
└────────────────────────────────────────────────────────────────┘
     ▲          ▲          ▲         ▲        ▲
     │          │          │         │        │
  SAM.gov  USASpending  Apify    SerpAPI   Anthropic
```

## 2. Tech stack decisions

### 2.1 Backend: Python 3.12 + FastAPI
- **Why Python:** best ecosystem for LLM work, data parsing (pandas, pdfplumber), and the GovCon community already ships Python scrapers.
- **Why FastAPI:** native async, OpenAPI docs for free, pydantic validation, deploys anywhere.
- **Package manager:** `uv` (10–100× faster than pip/poetry, deterministic lockfile).
- **ORM:** SQLAlchemy 2.0 async + Alembic migrations.

### 2.2 DB: PostgreSQL 16 + pgvector
- **Why Postgres, not Elasticsearch:** Postgres full-text search + pgvector covers 95% of our needs for 1/10 the operational burden. Escape to ES only if we hit a ceiling.
- **Why pgvector:** embed opportunities and capability statements, then nearest-neighbor search for semantic matching.
- **Row-level security (RLS):** every tenant-scoped table gets an RLS policy tied to a session variable set from the JWT. This is our second line of defense against tenant bleed.

### 2.3 Cache / Queue: Redis 7 + Celery
- **Celery over RQ:** Celery handles retry logic, scheduled tasks (Celery Beat), and failure modes better. The boilerplate is worth it.
- **Alternative considered:** Temporal.io. Overkill for MVP, revisit Year 2 if workflows get complex.

### 2.4 Frontend: Next.js 14 + TypeScript + Tailwind + shadcn/ui
- **Why Next.js:** App Router + Server Components cut boilerplate. Vercel-native but we can self-host on Fly.io.
- **Why shadcn/ui over Material / Chakra:** own the code, match MacTech's sober brand, no framework bloat.
- **Data fetching:** TanStack Query. No client-side Redux — use server components + React Query for client state.
- **Charts:** Recharts for the common stuff, Tremor for dashboards.

### 2.5 Auth: Clerk (MVP) → Auth.js + SAML (Year 2)
- **Why Clerk for MVP:** ship faster, org/tenant model built-in, JWT templating for RLS.
- **Why not Auth0:** 3× the price at our scale.
- **Migration path:** Clerk → Auth.js is a 1–2 week swap when enterprise SSO becomes a constant ask.

### 2.6 AI: Anthropic Claude (primary) + Voyage embeddings
- **Primary model:** Claude Sonnet 4.6 for everything that isn't speed-critical; Claude Haiku 4.5 for high-volume scoring.
- **Backup / arbitrage:** OpenAI GPT-4o, DeepSeek. Abstract behind a `LLMClient` interface.
- **Embeddings:** Voyage voyage-3 (cost-effective, high quality). OpenAI text-embedding-3-large as fallback.
- **Vector dim:** 1024. Matches `voyage-3` native output and `voyage-3-large` default. Both are Matryoshka-reducible to 512/256 later without a schema migration. Do not use 1536 — that was OpenAI `text-embedding-ada-002`, now deprecated.

### 2.7 Storage: S3-compatible
- **Dev:** MinIO in docker-compose.
- **Prod Year 1:** Cloudflare R2 (no egress fees, S3-compatible).
- **Prod Year 2+:** AWS GovCloud S3 once we handle customer CUI. Must happen before enterprise tier or CMMC Readiness Engine ships.

### 2.8 Infra / Deploy
- **Local dev:** docker-compose (Postgres, Redis, MinIO, dev mail catcher).
- **Early prod:** Fly.io (multi-region, cheap, Postgres add-on, good DX) or Railway.
- **Year 2+:** AWS GovCloud migration. Track cost and complexity carefully.
- **CI:** GitHub Actions — lint, type-check, test, build, deploy on main.

### 2.9 Observability
- **Errors:** Sentry (self-hosted option for GovCloud later).
- **Analytics:** PostHog self-hosted.
- **Uptime:** Better Stack or UptimeRobot.
- **Logs:** structured JSON, shipped to Axiom or Grafana Loki.

## 3. Multi-tenancy model

Two patterns in play:

- **Tenant-scoped rows** for most domain data (opportunities cached per tenant's saved filters; pursuits; documents; capability statements).
- **Shared reference data** for public-domain facts (the raw opportunity ingested from SAM.gov, the raw award from USASpending). This is deduplicated once and referenced by tenant-scoped tables.

Every query runs with a Postgres session variable `app.tenant_id` set from the authenticated user's JWT. RLS policies on every tenant-scoped table enforce `tenant_id = current_setting('app.tenant_id')::uuid`. The ORM layer additionally filters by tenant at the session level as belt-and-suspenders.

For MacTech's internal use in Year 1, MacTech is simply tenant #1.

## 4. AI layer architecture

LLM calls are expensive and slow. Design rules:

1. **Structured output only.** Every LLM call returns validated JSON against a Pydantic schema. No free-text responses into production code paths.
2. **Cache aggressively.** Hash the input, cache the output in Redis for 7–30 days depending on the call.
3. **Tiered models.** Haiku for scoring and classification; Sonnet for drafting and complex parsing. Expose this via a `complexity` parameter on the internal LLM client.
4. **Human-in-the-loop for outputs.** Sources Sought drafts, proposal shred-outs, and compliance matrices are always presented as drafts requiring human review. Never auto-submit.
5. **Prompt versioning.** Every prompt template lives in `packages/intelligence/prompts/` with a version number. Changes to prompts are PRs.

## 5. Data flow for a canonical opportunity

```
SAM.gov API
    │ noticeId=ABC123 JSON
    ▼
[ingest worker]
    │ upsert into public.opportunities_raw
    │ publish "opportunity.ingested" event → Redis
    ▼
[embedding worker]
    │ compute Voyage embedding of description
    │ upsert into public.opportunities_raw.embedding
    │ publish "opportunity.embedded" event
    ▼
[enrichment worker]
    │ lookup incumbent via USASpending search
    │ check exclusions via SAM.gov Exclusions API
    │ upsert into public.opportunities_enriched
    │ publish "opportunity.enriched" event
    ▼
[scoring worker] (per tenant)
    │ for each tenant:
    │   compute score = f(NAICS match, keyword match, set-aside fit,
    │                     ceiling sanity, incumbent weakness, founder fit)
    │   upsert into tenant_X.opportunity_scores
    │   if score > user threshold: enqueue notification
    ▼
[notification worker]
    │ email / SMS / Slack
```

## 6. Security posture

- TLS 1.3 end-to-end (Cloudflare in front of Fly.io).
- Secrets in environment only; no `.env` committed; use Doppler or 1Password for shared secrets.
- API keys for external services stored in a dedicated `external_credentials` table, encrypted at rest with AWS KMS (or age/passphrase for self-hosted).
- Rate limiting on every public API endpoint (nginx / Caddy layer + app-level).
- Request signing for internal worker → API calls.
- CSP headers strict on the web app.
- Every mutation logged to `audit_log` (append-only, 7-year retention).
- Weekly dependency audit (`uv pip audit`, `pnpm audit`).
- Monthly rotation of admin credentials.

## 7. Scaling plan

- **10 tenants, 10k opps/week:** single Postgres, single Redis, 2 API pods, 3 worker pods. Fly.io small tier.
- **100 tenants, 100k opps/week:** read replica Postgres, Redis Cluster, horizontal worker scaling, pgbouncer.
- **1000 tenants, 1M opps/week:** split ingestion to dedicated DB, consider Elasticsearch for search, move AI traffic to batch APIs where possible.

## 8. Migration to GovCloud (Year 2)

Trigger conditions (any one of):
- Enterprise customer requires FedRAMP Moderate ATO
- CMMC Readiness Engine stores customer CUI
- Annual revenue > $2M

Target architecture: AWS GovCloud with FedRAMP-aligned components (RDS Postgres, ElastiCache Redis, S3, ECS or Lambda). Estimated migration cost: 3–4 months engineering effort, $50k–$150k cloud spend ramp.

## 9. Known risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SAM.gov API rate limits tighten | Medium | High | Cache aggressively; negotiate higher quota; plan for secondary feeds |
| LLM cost spike | Medium | Medium | Cache + tiered models; budget alerts at $500/mo |
| Tenant data leak via RLS bug | Low | Catastrophic | Two-layer enforcement (app + DB); automated tests per tenant boundary |
| Incumbent buys us out cheap | Low | Medium | Focus on MacTech wins first — product funded by contract revenue, not investor dilution |
| CMMC 2.0 requirements change | Medium | Medium | Design the Readiness Engine around NIST controls, not CMMC specifics |
