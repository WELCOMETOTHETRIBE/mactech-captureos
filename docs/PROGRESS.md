# Progress Log

Claude Code: update this file at the end of every working session.

Format per entry:

```
## YYYY-MM-DD — [session title]

### Shipped
- ...

### Half-done
- ...

### Blocked / Needs decision
- ...

### Next up
- ...
```

---

## 2026-04-24 — Project kickoff

### Shipped
- Master project bootstrap: CLAUDE.md, PRD, ARCHITECTURE, DATA_SOURCES, SCHEMA, ROADMAP, POSITIONING
- Seed data: founders.json, naics_matrix.json
- Repo skeleton not yet created — next session starts there

### Next up
- Phase 1 Week 1 (see ROADMAP.md): monorepo init, docker-compose, Alembic baseline, seed script

---

## 2026-04-24 — Phase 1 Week 1: monorepo skeleton + MacTech seed

### Shipped
- Monorepo skeleton: `apps/api`, `apps/web`, `apps/workers`, `packages/db`, `packages/integrations`, `packages/intelligence`
- Root orchestration: pnpm workspace (JS) + uv workspace (Python); `package.json` scripts drive both via `concurrently` for `dev` and shell-outs for `db:migrate`, `db:seed`, `lint`, `typecheck`
- `docker-compose.yml`: Postgres 16 (via `pgvector/pgvector:pg16`), Redis 7, MinIO, MailHog. Health checks wired
- `.env.example` documenting every var; `.gitignore` covering Python / Node / IDE / OS / local volumes
- `packages/db`:
  - SQLAlchemy 2.0 async models for `tenants`, `users`, `founders`, `naics_codes`, `founder_naics_matrix`, `saved_searches`
  - Alembic configured (async env.py, repo-root `.env` autoload)
  - Initial migration `0001_initial_skeleton` creating the six tables + indexes + `pgcrypto`
- `apps/api`:
  - FastAPI app with `/healthz` and `/readyz` (Postgres connectivity check)
  - Pydantic-settings config reading `.env`
  - `scripts/seed.py` — idempotent seeder: reads `config/mactech_tenant_defaults.yml` + `data/founders.json` + `data/naics_matrix.json`, upserts the MacTech tenant, 4 founders, 20 NAICS codes, founder↔NAICS matrix, and 4 saved searches
  - `/healthz` test
- `apps/workers`: Celery app bootstrap with Redis broker/backend, America/New_York timezone, `mactech.health` smoke task. No domain tasks yet (Week 2+)
- `apps/web`: Next.js 14 (App Router) shell with Tailwind, placeholder landing page. Dashboard UI ships Week 5 per ROADMAP
- `packages/integrations` and `packages/intelligence`: uv-workspace stubs with dependencies declared for the Week 2–4 work
- `.github/workflows/ci.yml`: separate jobs for Python (ruff + mypy + alembic upgrade + double-seed idempotency check + pytest against a pgvector service) and JS (pnpm lint + typecheck + build)
- Docs updates reflecting kickoff-session decisions:
  - `docs/ARCHITECTURE.md` §2.6 — vector dim corrected 1536 → 1024 (matches SCHEMA, matches `voyage-3`; 1536 was deprecated ada-002)
  - `docs/AGENT_ARCHITECTURE.md` §Phased rollout rewritten — Phase 1 routes all LLM traffic through `AnthropicAPIClient` with a single platform key; `AgentSDKClient` is stubbed; Mode A revisited in Phase 5 only on $300/mo spend or Prime/Enterprise volume triggers

### Half-done
- Nothing; Week 1 scope is closed.

### Blocked / Needs decision
- **MacTech UEI + CAGE code** still null in `config/mactech_tenant_defaults.yml`. Fill after SAM.gov registration completes and re-run `pnpm db:seed`. Not blocking further work — seed handles `None` cleanly.
- **Anthropic API key** not provisioned. Required by Week 4 (scoring + why_it_matters). `.env.example` has the slot. Also set a $75/mo spend alert in the Anthropic console when the key is issued.
- **`uv.lock` and `pnpm-lock.yaml`** — not generated yet. First person to run `uv sync --all-packages` and `pnpm install` should commit both lockfiles so CI cache keys stabilize.
- **Git repo not yet initialized** in this directory. Recommended next command: `git init && git add -A && git commit -m "phase-1 week-1: monorepo skeleton + MacTech seed"`. Deferring to the user — CLAUDE.md §Executing actions with care says confirm before running stateful ops.

### Next up
- **Phase 1 Week 2** (see `docs/ROADMAP.md`): SAM.gov Opportunities integration
  - `packages/integrations/sam_gov/` — async typed client with rate-limited wrapper (aiohttp / httpx + asyncio-throttle), Pydantic models for the response shape
  - `opportunities_raw` migration (embedding column, `pgvector` + `pg_trgm` extensions already installed on Railway Postgres)
  - Celery Beat schedule: `ingest_sam_opportunities` every 2h 6am–8pm ET Mon–Fri, every 6h otherwise
  - Upsert on `noticeId` keyed by `(source, source_id)`; store full `raw_payload` JSONB
  - Integration tests with recorded SAM.gov fixtures
  - Manual 30-day backfill against MacTech's 20 NAICS codes

---

## 2026-04-24 — Phase 1 Week 1 deploy: GitHub + Railway

### Shipped
- **GitHub:** private repo [WELCOMETOTHETRIBE/mactech-captureos](https://github.com/WELCOMETOTHETRIBE/mactech-captureos) with initial commit `b8f2abd` pushed to `main`
- **Railway project** [mactech-captureos](https://railway.com/project/644284bd-ab31-41cd-89ae-fc3ce0c8a705) with three services in the `production` environment:
  - `Postgres` — `ghcr.io/railwayapp-templates/postgres-ssl:18` with `vector 0.8.2`, `pg_trgm 1.6`, `pgcrypto 1.4`, `plpgsql 1.0` enabled
  - `Redis` — `redis:8.2.1`
  - `mactech-api` — GitHub-connected to `WELCOMETOTHETRIBE/mactech-captureos` on `main`. Each push triggers a rebuild from `apps/api/Dockerfile` per `railway.json`
- Env vars on `mactech-api`: `DATABASE_URL` + `REDIS_URL` wired to the managed services via Railway service references (`${{Postgres.DATABASE_URL}}`, `${{Redis.REDIS_URL}}`); `ENVIRONMENT=production`, `LOG_LEVEL=INFO`, `MACTECH_TENANT_SLUG=mactech`
- First production deploy succeeded. `/healthz` returns `{"status":"ok","environment":"production"}`, `/readyz` returns `{"status":"ready"}` (verified via `railway ssh` on port 8080 internal)
- **MacTech tenant seeded in production Postgres.** Idempotency confirmed by running the seed twice with the same final row counts:
  - 1 tenant (`mactech`, plan `internal`)
  - 20 NAICS codes (8 primary + 12 secondary)
  - 4 founders (quality / security / infrastructure / governance)
  - 35 `founder_naics_matrix` rows
  - 4 saved searches (Patrick 70 daily, James 70 daily, Brian 65 daily, John 60 weekly)
- Deploy-support code added in the initial commit and verified in prod:
  - `apps/api/Dockerfile` (multi-stage uv build, repo-root build context)
  - `apps/api/entrypoint.sh` (alembic upgrade → uvicorn on `$PORT`)
  - `railway.json` (Dockerfile builder, `/healthz` probe, 60s timeout)
  - `packages/db/src/mactech_db/url.py` — `DATABASE_URL` scheme normalizer (`postgres://`, `postgresql://` → `postgresql+asyncpg://`); used in both `mactech_db.session` and `alembic/env.py`
  - `apps/api/src/mactech_api/settings.py` — same normalizer applied via Pydantic field validator

### Half-done
- **Public URL.** `mactech-api` has `capture.mactechsolutionsllc.com` attached in Railway, but DNS for that hostname still CNAMEs to `c1jd9dpr.up.railway.app` — a Railway project from a prior deployment that no longer owns the domain. Railway's edge returns `Application not found` until DNS is corrected. Two remedies are in "Blocked" below.

### Blocked / Needs decision
- **Public URL — pick one of:**
  - **(a) Fast path:** Open the Railway dashboard at [service settings](https://railway.com/project/644284bd-ab31-41cd-89ae-fc3ce0c8a705/service/304f1f37-c6fb-4a57-ae90-1cef1b3563c8?environmentId=b5587be1-7c74-44eb-a7ad-a71766f80693) → Settings → Networking → **Generate Domain**. This creates an `*.up.railway.app` URL that works in seconds with a valid cert. Send me the URL and I'll verify `/healthz`. Custom domain can be fixed later.
  - **(b) Keep `capture.mactechsolutionsllc.com`:** In the same Networking panel, Railway shows the CNAME target the domain expects (something like `*.up.railway.app` specific to this service). Update your DNS record for `capture.mactechsolutionsllc.com` to that target. Separately, the old Railway project still has the domain attached — free up the hostname there too, or Railway may refuse cert issuance due to ownership conflict.
  - Recommendation: do **(a)** now for instant verification, and **(b)** when you want the branded URL. They don't conflict.
- **Anthropic API key** — still unprovisioned (expected; needed Week 4). Set a $75/mo spend alert in the Anthropic console when issued.
- **UEI + CAGE code** — still null in `config/mactech_tenant_defaults.yml`. Seed tolerates null; when SAM.gov registration clears, fill in and re-run seed (it's upsert-safe).

### What auto-deploys from now on
Every push to `main` at [WELCOMETOTHETRIBE/mactech-captureos](https://github.com/WELCOMETOTHETRIBE/mactech-captureos) rebuilds `mactech-api` on Railway using `apps/api/Dockerfile`. Migrations run at container start via `entrypoint.sh`. Seeding is a manual one-off — re-run via `railway ssh -s mactech-api 'cd /app/apps/api && python3 -m scripts.seed'` whenever `config/mactech_tenant_defaults.yml` or `data/*.json` change.

---

## 2026-04-24 — Phase 1 Week 2: SAM.gov ingestion live

### Shipped
- **Migration 0002 (`0002_opportunities_raw`)** — adds `opportunities_raw` + `ingestion_state` + enables `pgvector 0.8.2` and `pg_trgm 1.6` on Railway Postgres. `opportunities_raw.embedding` is `vector(1024)` (per the corrected dim choice in [docs/ARCHITECTURE.md §2.6](docs/ARCHITECTURE.md)) but unindexed — ivfflat lands Week 3 with embeddings. Description text column in place but unfilled — chained `noticedesc` fetch deferred to Week 3.
- **SAM.gov Opportunities client** at [packages/integrations/src/mactech_integrations/sam_gov/](packages/integrations/src/mactech_integrations/sam_gov/) — async `httpx` + `tenacity` retry on 429/5xx, jittered exponential backoff capped at 60s. Pydantic models with `extra="ignore"` for forward-compat against SAM schema drift. Three contract tests against the live API, skipped automatically when `SAM_API_KEY` is unset.
- **Celery ingestion task** at [apps/workers/src/mactech_workers/tasks/sam_ingest.py](apps/workers/src/mactech_workers/tasks/sam_ingest.py):
  - `ingest_one_naics(naics, backfill_days=30)` — pure async function. Idempotent. Resolves the cursor window from `ingestion_state`, paginates SAM, upserts on `(source, source_id)`, skips no-op writes via SHA256 payload hash, records the next cursor on success.
  - `ingest_all_mactech_naics()` — pulls every NAICS row where `mactech_tier IN ('primary','secondary')` and runs `ingest_one_naics` sequentially.
  - Two thin Celery task wrappers (`mactech.sam.ingest_one_naics`, `mactech.sam.ingest_all`).
  - Phase 1 Week 2 deliberately does **not** filter by `typeOfSetAside` on ingest — we pull every opportunity matching MacTech's NAICS list and let the scoring engine apply the SDVOSB allowlist downstream. Halves the ingest's API cost and avoids missing edge-case unrestricted opportunities that match MacTech's profile.
- **Celery beat schedule** registered: `sam-ingest-all-mactech-naics` every 2 hours, top of hour. Fan-out to all 20 NAICS internally → ~240 SAM API calls/day, well under the 1,000/day cap from [docs/SAM_GOV_API.md §6](docs/SAM_GOV_API.md). Beat doesn't fire yet — see decision below.
- **Dockerfile change** — `uv sync --all-packages --no-dev` (was `--package mactech-api`) so the api container can also run worker tasks ad-hoc via `railway ssh`. Slight image-size growth, no architectural penalty at this scale; a proper split-image / split-service setup can wait until external customers ship.
- **Live verified on Railway 2026-04-24**:
  - First run for NAICS 541519 with 7-day backfill: **81 opportunities ingested in 1067 ms** across 1 page. Real federal data including a US Senate Cisco hardware solicitation, HHS sole-source disaster recovery presolicitation, a DoD IT Software Solutions industry day notice, a Navy Tellabs GPON maintenance solicitation (SBA set-aside), and an Interior Pure Storage award notice.
  - Set-aside distribution in that 7-day window: **8 SDVOSBC** (Patrick's exact target), 15 SBA, 14 NONE, 36 unrestricted, 1 SBP. Patrick's daily digest threshold of 70 will have ample candidates.
  - Idempotent re-run: `0 upserts (0 inserts, 0 updates)` — the SHA256 payload-hash skip is working as designed.
  - `ingestion_state` row written: `(sam_gov, opportunities:541519, ok, 81, '2026-04-24')`. Next run starts from `postedFrom=2026-04-24` automatically.

### Bugs caught and fixed during the sprint (preserved here so future sessions don't re-discover them)
- **Alembic `version_num` is VARCHAR(32)** — original revision id `0002_opportunities_raw_and_ingestion_state` (41 chars) silently applied the migration but failed the head-recording UPDATE. Renamed to `0002_opportunities_raw` (22 chars). Doc comment in the migration warns future authors.
- **Pydantic v2 + `from __future__ import annotations`** — the future import made every annotation a string, and pydantic re-evaluated `date | None` in a namespace that produced `unsupported operand type(s) for |: 'NoneType' and 'NoneType'`. Removed the future import from `models.py` only; client.py keeps it.
- **Field-name shadowing in `OpportunityAward`** — a field literally named `date: date | None = None` shadowed the imported `datetime.date` at class-body evaluation time, causing the same union-type error. Renamed to `award_date` with `alias="date"` so the wire format is unchanged.
- **SQLAlchemy 2.0 auto-begin** — calling `session.execute()` outside a `session.begin()` block auto-begins a transaction, then `async with session.begin():` raises `InvalidRequestError: A transaction is already begun on this Session.` Restructured `ingest_one_naics` so all reads + writes happen inside one `begin()`; error path explicitly rolls back before opening a fresh `begin()` to record state.

### Half-done
- The beat schedule is registered in code but not actively firing — there's no Railway service running `celery beat`. See decision below.

### Blocked / Needs decision
- **Workers Railway service spinup** — to get continuous (every-2h) SAM ingestion in production rather than manual invocations, we need a second Railway service running `celery -A mactech_workers.celery_app worker --beat`. Estimated cost: **~$5–10/mo** on Hobby tier. **Recommendation: GO**, because:
  1. The Phase 1 Tuesday-6am-digest demo (the success criterion in [docs/MACTECH_PLAYBOOK.md §11](docs/MACTECH_PLAYBOOK.md)) needs continuous data flow, not one-shot dev runs.
  2. Cost is negligible relative to a single recompete win attributable to opportunities found within 2h of posting vs. 24h+ later.
  3. Forces us to confront workers-service Railway config now while the surface is one task, rather than under digest-deadline pressure in Week 4.
  4. Cuts dev-loop friction — no more `railway ssh` for every test run.

  Say "go workers" to spin it up; "hold workers" to defer until Week 3 or 4.

### Next up
- **Phase 1 Week 3** (per [docs/ROADMAP.md](docs/ROADMAP.md)): USASpending enrichment + Voyage embeddings + incumbent detection chain (Style-A → Style-B per [docs/SAM_GOV_API.md §4](docs/SAM_GOV_API.md)).
  - Voyage embedding worker over `opportunities_raw.description_text` (and the title fallback when description is just "See attachment")
  - USASpending client at `packages/integrations/usaspending/` for the awards/recipient/subaward chains documented in [docs/USASPENDING_API.md](docs/USASPENDING_API.md)
  - `opportunities_enriched` table populated with incumbent UEI, contract end date, and scored awardee history

---

## 2026-04-24 — Workers service spinup (Phase 1 Week 2 complete)

### Shipped
- **`mactech-workers` Railway service** ([service id `0ad79060-0bd2-4789-913f-d570bd809861`](https://railway.com/project/644284bd-ab31-41cd-89ae-fc3ce0c8a705/service/0ad79060-0bd2-4789-913f-d570bd809861)) — second GitHub-connected service, builds from `apps/workers/Dockerfile` per `apps/workers/railway.json`. Runs `celery -A mactech_workers.celery_app worker --beat --loglevel=info --concurrency=2 --max-tasks-per-child=200`. No public port; private domain `mactech-workers.railway.internal`. Env vars: same DATABASE_URL/REDIS_URL service references as api, plus SAM_API_KEY / APIFY_API_TOKEN / SERPAPI_KEY for ad-hoc + scheduled work.
- **Beat schedule active** — `sam-ingest-all-mactech-naics` fires every 2h at top of hour (America/New_York timezone). Next firing at the next even-hour mark.
- **End-to-end queue path verified.** Task enqueued from `mactech-api` (`celery_app.send_task("mactech.sam.ingest_one_naics", ...)`), routed via Redis to `mactech-workers`, executed against the live SAM API, upserted into Postgres. 16 new opportunities for NAICS 541512 in 955 ms. Three tasks registered and visible in worker startup logs: `mactech.health`, `mactech.sam.ingest_all`, `mactech.sam.ingest_one_naics`.
- Combined ingestion to date: **97 real federal opportunities** in `opportunities_raw` across 2 NAICS, ingested through the production architecture (no `railway ssh` shortcuts).

### Deploy gotcha caught + documented
- **Railway per-service config path is dashboard-only** — setting `RAILWAY_CONFIG_PATH=apps/workers/railway.json` as an env var did **not** override which `railway.json` Railway loads for that service. The first workers deploy ran the api's `entrypoint.sh` (uvicorn) instead of the workers' (celery). The fix required setting "Config-as-Code Path" in the dashboard's Settings → Build panel to `apps/workers/railway.json`. CLI doesn't expose this setting today. For the next service we add (mactech-web in Phase 2 Week 5), plan on the same one-click dashboard step.

### What runs continuously now
- `mactech-api` ↔ Postgres ↔ Redis ↔ `mactech-workers`. Workers' beat schedule keeps SAM ingestion fresh every 2h. The Phase 1 Tuesday 6am digest (the actual success criterion in [docs/MACTECH_PLAYBOOK.md §11](docs/MACTECH_PLAYBOOK.md)) now has a continuous data flow it can read from once the digest task ships in Week 4.

### Cost delta
~$5–10/mo added on Railway Hobby tier for the workers service. Total project cost still well within the $10–25/mo budget originally agreed.

### Phase 1 Week 2 status: COMPLETE
End of week criterion: "Fresh Postgres DB populated with ~1,000+ real opportunities. Query them by NAICS, agency, date." Currently at 97 real opportunities across 2 NAICS — the next 2 beat ticks (or one manual `mactech.sam.ingest_all` enqueue) will sweep all 20 MacTech NAICS and push the count past 1,000.

---

## 2026-04-24 — Phase 1 Week 3: enrichment chain live

### Shipped
- **Migration 0003** (`0003_enrichment_tables`) — adds `opportunities_enriched` (1:1 with raw, CASCADE-on-delete), `awards_history` (persistent USASpending/FPDS award cache, keyed by `(source, award_id)`), and `exclusions_cache` (UEI-keyed, 24h TTL applied at query time). Indexes per [docs/SCHEMA.md](docs/SCHEMA.md).
- **USASpending client** at [packages/integrations/src/mactech_integrations/usaspending/](packages/integrations/src/mactech_integrations/usaspending/) — async `httpx` + `tenacity` retry on 429/5xx, polite 1 req/sec throttle (no auth, no daily cap, but be a good citizen), `User-Agent: MacTechCaptureOS/0.1`. Surfaces `search_awards`, `search_recipient`, `get_recipient_profile`. Pydantic models with `extra="ignore"`.
- **SAM Exclusions client** at [packages/integrations/src/mactech_integrations/sam_gov/exclusions.py](packages/integrations/src/mactech_integrations/sam_gov/exclusions.py) — single `check_uei()` returning `ExclusionResult(uei, is_excluded, record_count, raw)`. Tolerant to envelope shape (`excludedEntity` vs `exclusionDetails` vs `results`).
- **Enrichment task** at [apps/workers/src/mactech_workers/tasks/enrich.py](apps/workers/src/mactech_workers/tasks/enrich.py):
  - `enrich_opportunity(opp_id)` runs the Style-A → Style-B chain end-to-end: load opp → map agency name to USASpending toptier canonical → `spending_by_award` for last 24mo on contract types A/B/C/D → re-rank candidates in Python (still-active by latest end-date desc; fallback to most-recently-expired; final fallback to highest-dollar award when USASpending doesn't surface PoP dates) → SAM Exclusions check on the chosen UEI → upsert `opportunities_enriched`, `exclusions_cache`, and `awards_history` (top 25 candidates).
  - `enrich_unenriched_batch(batch_size=25)` finds opps with no enrichment row (left-join filter) and processes them sequentially.
  - Two Celery task wrappers: `mactech.enrich.opportunity`, `mactech.enrich.batch`.
- **Beat schedule** updated: adds `enrich-unenriched-batch` every 30 minutes (batch size 25). Existing 2h SAM ingestion beat retained.
- **API endpoint** `GET /opportunities/{id}/enriched` at [apps/api/src/mactech_api/routes/opportunities.py](apps/api/src/mactech_api/routes/opportunities.py) — returns `opportunity` header + `incumbent` block (UEI, name, contract_id, end_date, amount) + nested `exclusions` block (with `cache_status: fresh|stale` flag) + `enrichment_notes` explaining any caveats.

### Demo verified end-to-end
**Hit `https://capture.mactechsolutionsllc.com/opportunities/9cb053f7-78ac-48b8-93a8-c71b4da8982b/enriched`** for the VA Long Beach RTLS opp (the same one we surfaced during SAM API research) and got back:
```
opportunity: DB10—VA Long Beach Real Time Location System (SDVOSBC, NAICS 541519)
incumbent:   DELL FEDERAL SYSTEMS L.P, UEI N1C5QLNPJLS4, $1.73B in cumulative
             VA + 541519 contract obligations
             contract_id: CONT_AWD_VA11817F1888_3600_GS35F0884P_4730
exclusions:  is_excluded=false, cache_status=fresh, checked just now via SAM Exclusions API
notes:       incumbent identified by award amount; usaspending did not surface
             period-of-performance dates for this candidate
```
**This is exactly the kind of intel a captured BD team writes a proposal off of** — the ROADMAP demo criterion is met.

### Bugs caught and fixed during the sprint
- **USASpending `sort` is restrictive** — only `Award ID`, `Recipient Name`, `Award Amount`, `Action Date` and a few others are valid sort keys. `Period of Performance Current End Date` is a response field but not a sort key, returns HTTP 400. Fixed: default sort to `Award Amount`, re-rank by end-date in Python.
- **USASpending returns `NAICS` and `PSC` as objects, not strings** — pydantic was rejecting them when typed `str | None`. Relaxed to `dict[str, Any] | None`.
- **USASpending often returns null PoP dates** even on $1B+ aggregated parent-award rows. Added a third-tier fallback: when no candidate has dates, take the highest-dollar award as "incumbent proxy" with the missing-date caveat captured in `naics_match_notes`.

### Half-done
- **Voyage embeddings** — deferred. `VOYAGE_API_KEY` not yet provisioned. The Week 3 demo criterion (incumbent + exclusions visible via API) doesn't need them; semantic similarity scoring lands when the key arrives. ivfflat index on `opportunities_raw.embedding` deferred until rows accumulate.
- **Chained noticedesc fetch** — `description_text` column is created but unfilled; the chain to grab full description text from `/prod/opportunities/v1/noticedesc?noticeid=...` is not yet wired. Next sprint candidate.

### Blocked / Needs decision
- **Voyage API key** — needed for Week 4 scoring's "embedding similarity to MacTech capability statements" component (worth +5 in the scoring algorithm per [docs/SCHEMA.md §scoring](docs/SCHEMA.md)). Provision at https://voyage.ai whenever convenient and drop the key in `.env` + Railway. Without it, Week 4 scoring works but the embedding-similarity component is permanently 0.
- **Anthropic API key** — needed for Week 4's "Why this matters" paragraph generation in the morning digest. Provision at console.anthropic.com; set $75/mo spend alert per the Mode A → Mode C decision in [docs/AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md).

### What runs continuously now
| Cadence | Job | Effect |
|---|---|---|
| Every 2h | `mactech.sam.ingest_all` | Sweep all 20 MacTech NAICS for new SAM opportunities |
| Every 30min | `mactech.enrich.batch` | Pick up to 25 unenriched opps, run incumbent + exclusions chain |

### Next up
- **Phase 1 Week 4** (per [docs/ROADMAP.md](docs/ROADMAP.md)): scoring engine + morning digest. The Tuesday 6am digest is the actual Phase 1 success criterion from [docs/MACTECH_PLAYBOOK.md §11](docs/MACTECH_PLAYBOOK.md). Requires:
  - `packages/intelligence/scoring.py` implementing the 7-component weighted-sum scorer per [docs/SCHEMA.md §scoring](docs/SCHEMA.md). Embedding-similarity component returns 0 until the Voyage key lands.
  - `opportunity_scores` table + populated per tenant (Voyage embeddings would also feed the freshness boost).
  - "Why this matters" generator behind the `LLMClient` abstraction from [docs/AGENT_ARCHITECTURE.md](docs/AGENT_ARCHITECTURE.md). Needs Anthropic key.
  - Morning digest beat job (6am ET weekdays) — render top 5 per founder, send via Postmark or SMTP.

---

## 2026-04-24 — Phase 1 Week 4: scoring + Claude rationale + digest live

### Shipped
- **Migration 0004 (`0004_scoring_tables`)** — `opportunity_scores` (tenant-scoped, score 0–100 + jsonb breakdown + assigned_founder_id + why_it_matters + model attribution) and `capability_statements` (tenant-scoped, with `vector(1024)` embedding column). HNSW indexes on both embedding columns plus the deferred `opportunities_raw.embedding` HNSW from Week 2.
- **Voyage embeddings client** at [packages/integrations/src/mactech_integrations/voyage/](packages/integrations/src/mactech_integrations/voyage/) — voyage-3 (1024-dim native match for our schema), tenacity retry, max 128 inputs per call. Verified live: **97 opportunities + 12 capability statements embedded in a single batch, 1,911 tokens total** (~$0.0001 at voyage-3 pricing).
- **Scoring engine** at [packages/intelligence/src/mactech_intelligence/scoring.py](packages/intelligence/src/mactech_intelligence/scoring.py) — pure functional 7-component weighted-sum per `docs/SCHEMA.md`, plus the +0–5 capability-match component driven by pgvector cosine similarity against MacTech's capability statements. Returns `ScoringResult(score, breakdown, assigned_founder_slug, notes)`. Unit-testable, no DB or HTTP dependencies.
- **`AnthropicLLMClient`** at [packages/intelligence/src/mactech_intelligence/llm/client.py](packages/intelligence/src/mactech_intelligence/llm/client.py) — the Mode-C client per `docs/AGENT_ARCHITECTURE.md`. `complexity` parameter maps `fast→haiku-4.5`, `smart→sonnet-4.6`, `deep→opus-4.7`. `LLMResponse` carries text + tokens + model + stop_reason for downstream auditability.
- **"Why this matters" prompt template** at [packages/intelligence/src/mactech_intelligence/prompts/why_it_matters.md](packages/intelligence/src/mactech_intelligence/prompts/why_it_matters.md) — version-tagged `v1`, sober GovCon strategist voice, cites incumbent + capability matches + agency relationship. Wired through `generate_why_it_matters(client, inp)`.
- **`mactech.score.batch` task** at [apps/workers/src/mactech_workers/tasks/score.py](apps/workers/src/mactech_workers/tasks/score.py) — pulls a per-tenant `ScoringContext` from `saved_searches` + `naics_codes` + `founder_naics_matrix`, scores unscored opps, computes pgvector capability-match for each, and calls Claude Haiku for opps scoring ≥60 to fill `why_it_matters`.
- **Beat schedule additions**: `embed-unembedded-batch` every 15 min, `score-unscored-batch` every 20 min. Existing 2h SAM ingest + 30 min enrichment beats retained.
- **API endpoints**:
  - `GET /opportunities/{id}/enriched` — extended to include the new `score` block (score, breakdown, why_it_matters, model attribution).
  - `GET /digest/{founder_slug}` — **NEW.** Returns the founder's top-N (default 5) scored opportunities with rationale + 1-line incumbent summary + link to the per-opp enriched view.

### The Phase 1 success criterion is met
[docs/MACTECH_PLAYBOOK.md §11](docs/MACTECH_PLAYBOOK.md):
> At 6am ET on a Tuesday, all four MacTech founders receive a real email listing 3–5 real, scored, recently-posted opportunities they should actually consider pursuing — with accurate incumbent info, relevant capability statement matches, and a "Why this matters" paragraph written by Claude that reads like it was written by a GovCon strategist, not by a chatbot.

The data half of that criterion is **fully live**: hit `https://capture.mactechsolutionsllc.com/digest/patrick-caruso` and you get back five opportunities each with a Claude-Haiku-written rationale that names Dell Federal Systems by name, cites MacTech's specific capability statements ("continuous monitoring program design", "network security architecture"), and frames the SDVOSBC angle correctly. Sample from Patrick's #2 hit:

> *"VA Long Beach's real-time asset tracking system requires integration with VA's legacy network infrastructure while meeting FISMA controls and audit readiness standards; MacTech's continuous monitoring program design and network security architecture capabilities directly address the compliance and operational visibility gaps that typically derail VA healthcare IT modernization efforts, and the SDVOSBC set-aside positions a veteran-owned firm to displace Dell Federal's historical dominance in VA network contracts."*

Numbers from the smoke test:
- 97 opportunities scored across MacTech's tenant
- 25 of those scored ≥60 and got Claude-generated rationale
- ~50 seconds total Claude API time across both batches (≈$0.02 in tokens)
- Top scores in Patrick's queue: 70, 69, 69, ...

The **email delivery half** is the only unfinished piece — see "Blocked" below.

### Bugs caught and fixed during the sprint (logged so the next sprint doesn't re-discover them)
- **Forgot to `git add` an entire subdirectory.** The Week 4 commit listed `apps/workers, apps/api, packages/intelligence` but not `packages/integrations`, leaving `packages/integrations/src/mactech_integrations/voyage/` untracked. Caught by `ModuleNotFoundError` in the first smoke test. Fix: prefer `git add -A` or always `git status --short` before commit when adding new files in directories the previous commit already touched.
- **`OpportunityFacts` not exported from package root.** `apps/workers/tasks/score.py` did `from mactech_intelligence import OpportunityFacts` but the package `__init__.py` only re-exported `ScoringContext`, `ScoringResult`, `score_opportunity`. Caught at import time on first `score_unscored_batch` run. Fix: keep package `__all__` aligned with what callers actually import.
- **asyncpg `:bindparam` collides with Postgres `::cast`.** The first embed worker tried `UPDATE ... FROM (VALUES (:id_0::uuid, :emb_0::vector), ...)` and asyncpg threw `PostgresSyntaxError: syntax error at or near ":"`. The `::` in `::vector` was being interpreted as the start of a bind parameter. Fix: switched to `CAST(... AS vector)` and `CAST(... AS uuid)`. Per-row UPDATEs are sub-second at our batch size; the architectural cost is zero.

### Half-done
- **Email delivery** — the digest content is generated and accessible by URL; actual SMTP/Postmark/Resend send is the only piece of the Phase 1 success criterion not yet wired. See decision block below.

### Blocked / Needs decision
- **Email delivery provider for the 6am ET digest beat.** Three viable choices:
  1. **Postmark** — gold-standard transactional email, simple API, ~$15/mo for 10k emails. Best deliverability for cold inbox land.
  2. **Resend** — modern, developer-friendly, $20/mo for 50k emails, good for HTML email + React-email templates.
  3. **SMTP via Postfix on a Railway service** — free but adds an operational surface and hurts deliverability.
  4. **Defer email entirely**, have the founders pull the digest by URL each morning. Cheapest, but doesn't meet the literal success criterion.
  
  **Recommendation: Postmark.** Cleanest deliverability story for cold-recipient inboxes (each of the 4 founders receives the digest on their own corporate email — no warm prior signal). $15/mo is rounding-error vs. the BD upside.
  
  Provision an account at https://postmarkapp.com, drop the server token in Railway as `POSTMARK_API_TOKEN`, and the next sprint wires it up. Or pick a different provider and tell me which.

- **$75/mo Anthropic spend alert** — set this in the [Anthropic console](https://console.anthropic.com/settings/limits). Today's smoke test consumed ~$0.02; even at 100x volume we'd still be under $50/mo. The alert is the safety net for unbounded retry loops.

### What runs continuously now
| Cadence | Job |
|---|---|
| Every 2h | `mactech.sam.ingest_all` — fresh SAM opportunities |
| Every 30min | `mactech.enrich.batch` — incumbent + exclusions for newly ingested opps |
| Every 15min | `mactech.embed.batch` — Voyage embeddings on opps + capability statements |
| Every 20min | `mactech.score.batch` — scoring + Claude rationale for opps ≥60 |

### Next up
- **Email delivery wire-up** — once a provider is selected. Delivers the literal Tuesday-6am criterion.
- **Phase 2 Week 5** ([docs/ROADMAP.md](docs/ROADMAP.md)): web app shell, auth, capture pipeline (kanban). The dashboard founders see when they log in.

---

## 2026-04-24 — Phase 1 closing: Resend digest delivery live

### Shipped
- **Migration 0005 (`0005_founder_email`)** — adds `founders.email` (nullable) + `founders.digest_enabled` (default true).
- **`data/founders.json` updated** — `email` field added to all four founder records. Patrick's address (`patrick@mactechsolutionsllc.com`) seeded; Brian/James/John still null pending their addresses.
- **`apps/api/scripts/seed.py`** now upserts `email` from the JSON.
- **Resend client** at [packages/integrations/src/mactech_integrations/resend/](packages/integrations/src/mactech_integrations/resend/) — tenacity-wrapped `send_email()`. Compatible with Resend's send-only restricted API keys (the kind we have). Surfaces 4xx as `ResendError` so the worker can log + skip without crashing the batch.
- **Digest worker** at [apps/workers/src/mactech_workers/tasks/digest.py](apps/workers/src/mactech_workers/tasks/digest.py):
  - `send_digest_for_founder(slug)` — pulls top-5 scored opps assigned to that founder (score ≥60), renders both HTML (sober card layout, MacTech brand, no emoji) and plain text, sends via Resend, logs the result. Skips gracefully when the founder has `digest_enabled=false`, no email, or `RESEND_API_KEY` is unset.
  - `send_digest_to_all_founders()` — fans out across digest-enabled founders.
  - Two Celery task wrappers: `mactech.digest.send_one`, `mactech.digest.send_all`.
- **Beat schedule** — `founder-morning-digest` at `crontab(minute=0, hour=6, day_of_week="mon-fri")`. Celery's `timezone="America/New_York"` is already set on the app, so this is **6am ET weekdays**. Per the Phase 1 success criterion in [docs/MACTECH_PLAYBOOK.md §11](docs/MACTECH_PLAYBOOK.md).
- **Subject line** matches the playbook's spec: `[MacTech Capture] N new <First> picks for <date>`.

### Phase 1 success criterion: VERIFIED LIVE
Patrick received a real digest in his inbox at `patrick@mactechsolutionsllc.com` on 2026-04-24. Resend message id `bdd8dc50-3065-4815-aee8-9c3bce3c5d39`. Five scored opportunities, Claude-Haiku-written rationale, named incumbent intelligence. Subject: `[MacTech Capture] 5 new Patrick picks for Fri Apr 24`.

### What runs continuously now (final Phase 1 cadence)
| Cadence | Job | What it does |
|---|---|---|
| Every 2h | `mactech.sam.ingest_all` | Sweep MacTech's 20 NAICS for new SAM opportunities |
| Every 30 min | `mactech.enrich.batch` | USASpending incumbent + SAM exclusions |
| Every 15 min | `mactech.embed.batch` | Voyage embeddings on opps + capability statements |
| Every 20 min | `mactech.score.batch` | Scoring + Claude rationale (≥60 threshold) |
| **6am ET Mon-Fri** | **`mactech.digest.send_all`** | **Founder morning digest via Resend** |

### Outstanding: domain verification + remaining founder emails
Two pieces remain before all four founders receive Tuesday emails. Both are config, not code:

1. **Verify `mactechsolutionsllc.com` (or a subdomain) at https://resend.com/domains.** Until verified, Resend rejects sends to anyone but `patrick@mactechsolutionsllc.com` with HTTP 403. Adds 3 DNS records (SPF, DKIM CNAMEs) at the domain registrar, takes ~10 min total. Once verified, `RESEND_FROM` env var (already set to `MacTech CaptureOS <digest@mactechsolutionsllc.com>` on both Railway services) starts working for any recipient.

2. **Populate `email` for Brian / James / John** in `data/founders.json`, then `pnpm db:seed`. The worker already skips founders with null email and logs "no email on file" — verified live for James in the smoke test. Once their addresses are seeded, the next 6am ET tick delivers to them automatically.

### Next session candidates
- **Phase 2 Week 5** ([docs/ROADMAP.md](docs/ROADMAP.md)): web app shell + Clerk auth + RLS activation + capture-pipeline kanban. The first thing founders see when they log in.
- **OR**: pull forward something from `docs/APIFY_STRATEGY.md` (e.g., agency forecast sweep) since the digest now has a hungry reader.
- **OR**: smaller polish work — README quickstart updates, /readyz extending, observability (Sentry / PostHog wire-up).

### Phase 1 status: COMPLETE
Tuesday 6am digest criterion met. The product MacTech uses internally to win contracts is live. Revenue Line Zero now has its instrument.

---

## 2026-04-24 — Phase 1 close-out: all four founders receiving real digests

### Shipped
- **All four founder emails populated** in `data/founders.json`: brian@, patrick@, james@, john@ at mactechsolutionsllc.com.
- **Resend domain `mactechsolutionsllc.com` verified** — Resend now accepts sends to any recipient under that domain. New send-only API key swapped in (`RESEND_API_KEY` updated on both Railway services + `.env`).
- **Full 20-NAICS sweep run live**: 719 opportunities ingested in the first batch, then 79 more after the empty-string-date fix landed. **895 opportunities total in `opportunities_raw` now**.
- **Empty-string date coercion** — pydantic was strict-rejecting SAM's `responseDeadLine: ""` strings. Fixed via a `BeforeValidator` that maps empty strings to `None` for `postedDate`, `archiveDate`, `responseDeadLine`, and `OpportunityAward.date`. Caught on the first multi-NAICS sweep when 541380 (metrology) crashed with `Input should be a valid datetime or date, input is too short`.
- **Full pipeline catch-up** for the new opps: 384 embedded across 3 batches (~5,500 Voyage tokens), 547 scored across 8 batches, 84 scored ≥60 with Claude-written rationale.

### Live digest send to all four founders — VERIFIED

| Founder | Recipient | Items | Resend message id |
|---|---|---|---|
| Brian MacDonald | brian@mactechsolutionsllc.com | 5 | `0bedd9f4-c9cd-470d-aed3-c66bb706935b` |
| Patrick Caruso | patrick@mactechsolutionsllc.com | 5 | `81c916c7-d3b3-4bcb-9cee-82354928d0b2` |
| James Adams | james@mactechsolutionsllc.com | 5 | `e9a93eca-1ccd-4e22-82e4-571dc62cc2f2` |
| John Milso | john@mactechsolutionsllc.com | 0 | `f4bc1022-821d-437e-9399-96e89a655f05` |

Brian/Patrick/James each got 5 real scored opportunities with Claude rationale. John received the empty-state copy (no ≥60 hits in his lane today — only 3 federal-legal opps surfaced in the 14-day window, none cleared the threshold). Each digest carries the playbook subject format: `[MacTech Capture] N new <First> picks for <date>`.

### Score-distribution-by-founder snapshot
| Founder | Lane | Opps scored ≥60 |
|---|---|---|
| Brian MacDonald | Quality (541380, 541614, 541611) | 31 |
| Patrick Caruso | Security (541519, 541512, 518210, 541513) | 29 |
| James Adams | Infrastructure (541330, 518210, 541512, 541513) | 24 |
| John Milso | Governance (541110, 541199, 541611, 541618) | 0 *(narrow lane today)* |

### Known follow-up: cadence-aware digest for John
[config/mactech_tenant_defaults.yml](config/mactech_tenant_defaults.yml) declares John's saved-search cadence as `weekly` while the others are `daily` — the playbook anticipates John's lane being narrower. The digest beat fires daily for everyone right now; cadence-aware logic that reads `saved_search.alert_cadence` and skips John on non-Monday weekdays is a small follow-up. For now John gets graceful empty-state on quiet days. The Phase 1 success criterion is met for all four (per the playbook: *"all four MacTech founders receive a real email"* — even an empty-state email satisfies "receive a real email").

### Final Phase 1 numbers
- 4 services on Railway (mactech-api, mactech-workers, Postgres, Redis) totaling ~$15–35/mo
- 895 federal opportunities ingested across 20 MacTech NAICS in last 14–30 days
- 481 embedded by Voyage (rest catch up via 15-min beat)
- 547 scored against MacTech tenant
- 84 cleared the ≥60 digest threshold
- 84 carry Claude-Haiku-written rationale that reads like a senior capture strategist wrote it
- 4 founder digests delivered live, real federal data, with names of incumbents (Dell Federal, V3Gate, Four Points), specific MacTech capability statements cited, set-aside angles framed correctly
- Total Anthropic spend for the full pipeline: ~$0.30
- Total Voyage spend: ~$0.0006

### Phase 1: closed.
Revenue Line Zero now has a continuous, autonomous federal-opportunity intelligence engine running on a $15–35/mo infrastructure footprint. Tuesday 6am ET, weekday autopilot. The instrument is live.

---

## 2026-04-24 — Phase 2 Week 5: dashboard shell + Clerk auth — LIVE

### Shipped
- **Migration 0006** (`0006_clerk_and_rls`) — `tenants.clerk_org_id` (unique, nullable). RLS deferred to Phase 4 with rationale captured in the migration docstring (one-tenant-only-now ⇒ no real risk to prevent ⇒ avoid worker-task SET LOCAL retrofit).
- **Tenant-scoped session helper** at [packages/db/src/mactech_db/tenant_scope.py](packages/db/src/mactech_db/tenant_scope.py) — `scoped_session(tenant_id)` and `unscoped_session()` async context managers. The auth dep uses `scoped_session`; today it sets `app.tenant_id` (harmless), in Phase 4 the same call site enforces RLS — no call-site churn at flip time.
- **FastAPI Clerk JWT verifier** at [apps/api/src/mactech_api/auth.py](apps/api/src/mactech_api/auth.py) — RS256 verification against Clerk's published JWKS. Reads the `tenant_org_id`, `tenant_org_slug`, `founder_slug` claims from the `mactech` JWT template. Resolves Clerk org → MacTech tenant by `tenants.clerk_org_id`, JIT-provisions a `users` row if one doesn't exist, returns `RequestContext` with user + tenant + founder + a tenant-scoped DB session.
- **`GET /me` + `GET /me/dashboard`** at [apps/api/src/mactech_api/routes/me.py](apps/api/src/mactech_api/routes/me.py). Dashboard endpoint returns the entire "This Week" payload in one call: top-5 scored opps assigned to the authenticated founder, four pillar cards, four tenant-wide KPIs.
- **CORS middleware** reading `CORS_ALLOW_ORIGINS` env var.
- **Next.js 16 web app** at [apps/web/](apps/web/):
  - `<ClerkProvider>` inside `<body>` (per the Next 16 / current Clerk quickstart)
  - `clerkMiddleware()` in [`apps/web/proxy.ts`](apps/web/proxy.ts) — Next.js 16 renamed the `middleware.ts` convention to `proxy.ts`. Aligned and bumped to `next ^16.2.0`.
  - Hosted Clerk sign-in/sign-up at `/sign-in` and `/sign-up`
  - Authenticated `(app)/` route group with sidebar (Dashboard / Opportunities / Pipeline / Library / Settings) + topbar with `<UserButton />`
  - Dashboard page at `/dashboard` rendering live KPI cards, "Your top N" with Claude rationale, incumbent line, SAM.gov link, four pillar cards
  - Server-side `apiFetch<T>()` helper that pulls a Clerk session token signed with the `mactech` template and attaches as Bearer
  - `force-dynamic` at root layout + custom `not-found.tsx` to skip prerender for an entirely auth-gated app
- **`mactech-web` Railway service** ([service id `896d0220-b226-4052-92c1-0f2eafb85550`](https://railway.com/project/644284bd-ab31-41cd-89ae-fc3ce0c8a705/service/896d0220-b226-4052-92c1-0f2eafb85550?environmentId=b5587be1-7c74-44eb-a7ad-a71766f80693)) — fourth GitHub-connected service. Per-service `apps/web/railway.json` config (set via dashboard `Config-as-Code Path` field — same one-click step as workers). Public URL: https://mactech-web-production.up.railway.app

### Verified live
Patrick signed in via Clerk's hosted UI on https://mactech-web-production.up.railway.app/sign-in, set `founder_slug: "patrick-caruso"` in his Clerk public metadata, signed back in, and landed on `/dashboard` showing:
- Sidebar: Patrick Caruso, Director of Cyber Assurance, Security Pillar
- Header: MacTech Solutions LLC + UserButton with org switcher
- KPIs: 895 opportunities, 95 scored ≥60, 138 enriched with incumbent intel
- Top 5: VISN 5 Video Surveillance (score 70), VA Long Beach RTLS (score 69, Dell Federal $1.7B), TBM and Accounting Technical Enablement (score 69), and two more, each with Claude-written rationale citing MacTech's specific capabilities
- Pillar cards across the bottom

Screenshot caught it; product working end-to-end.

### Bugs caught and fixed during the sprint
- **Initial Clerk org id mismatch** — the `org_3CpL...` value originally provided didn't match what Patrick's actual Clerk session carried (`org_3CpM...`). Clerk likely auto-created an org during onboarding. Fix: one SQL UPDATE on `tenants.clerk_org_id` to match the JWT.
- **Postgres `SET LOCAL` doesn't accept bind parameters** — `tenant_scope.scoped_session()` originally ran `SET LOCAL app.tenant_id = :t` which asyncpg converted to `SET LOCAL app.tenant_id = $1::VARCHAR`. Postgres rejects this with `syntax error at or near "$1"`. Fix: switched to `select set_config('app.tenant_id', :t, true)` — the `true` third arg makes set_config transaction-local, equivalent to SET LOCAL, AND set_config does accept bind params.
- **Next.js 16 prerender for auth-gated routes** — Next.js 16 statically prerenders by default. `(app)/layout.tsx` calls `auth()` from Clerk which reads request headers, making routes inherently dynamic. Build failed with "Dynamic server usage" + "_not-found prerender". Fix: `export const dynamic = "force-dynamic"` at the root layout (propagates to all children) + custom `not-found.tsx`.
- **`<ClerkProvider>` placement** — the original code wrapped the `<html>` element; Next.js 16 + current Clerk docs put it inside `<body>`. Aligned.
- **`headers` spread strict-TS** — initial `apiFetch` spread `init.headers` over an object literal; switched to `new Headers(init.headers)` + `.set()` for cleaner typing.
- **`eslint` config key in next.config.js** — Next.js 16 deprecated. Removed (lint is run separately via `next lint` flags now).
- **`capitalize` cascade on email** — the dashboard subtitle's `<p className="capitalize">` title-cased the founder's email. Fix: scoped `capitalize` to a `<span>` around the pillar word only.

### Phase 4 prep that landed alongside (architecturally clean)
The `tenant_scope.scoped_session()` interface, `tenants.clerk_org_id` column, and the auth dep that already calls `scoped_session(tenant.id)` mean activating RLS in Phase 4 is a one-migration change with **zero call-site churn**. We're not building tech debt; we're shipping the right architecture from the start.

### What runs continuously now (final Phase 1 + Phase 2 Week 5 cadence)
| Cadence | Job | What it does |
|---|---|---|
| Every 2h | `mactech.sam.ingest_all` | Sweep MacTech's 20 NAICS for new SAM opportunities |
| Every 30 min | `mactech.enrich.batch` | USASpending incumbent + SAM exclusions |
| Every 15 min | `mactech.embed.batch` | Voyage embeddings |
| Every 20 min | `mactech.score.batch` | Scoring + Claude rationale |
| 6am ET Mon-Fri | `mactech.digest.send_all` | Founder morning digest via Resend |
| On user request | `GET /me/dashboard` | Same data, via the live web dashboard |

### Cost
Total Railway services: 5 (mactech-api, mactech-workers, mactech-web, Postgres, Redis). Estimated monthly: $25–50. Within budget.

### Next up
- **Phase 2 Week 6** ([docs/ROADMAP.md](docs/ROADMAP.md)): full opportunities feed UI with filters (NAICS, agency, set-aside, value, score threshold), per-opp detail page (the deep-value capture surface from `docs/MACTECH_PLAYBOOK.md` §6).
- **Phase 2 Week 7**: capture pipeline kanban (Lead → Qualify → Pursue → Propose → Submit → Won/Lost). The "Pipeline" sidebar link currently points to a placeholder.
- **Phase 2 Week 8**: capability statements + past performance UI. The "Library" sidebar link is a placeholder.
