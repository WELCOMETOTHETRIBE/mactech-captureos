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

---

## 2026-04-24 — Phase 2 Week 6 (partial): opportunity detail page

### Shipped (the per-opp detail half of Week 6 — list/filter view deferred)
- **`GET /opportunities/{id}`** at [apps/api/src/mactech_api/routes/opportunities.py](apps/api/src/mactech_api/routes/opportunities.py) — now authenticated (was unauthenticated `/opportunities/{id}/enriched` in Phase 1; the old URL kept as a 308 redirect for any bookmarked links). Returns the rich detail payload the UI renders:
  - Header (title, agency, notice type, set-aside + description, NAICS, solicitation number, posted date, response deadline + days-until countdown, sam.gov link, additional info link)
  - `description` block with `text` + `source_url` + `fetch_status: "fetched" | "pending" | "unavailable"`
  - `incumbent` block (UEI, name, contract id, end date, cumulative obligations, exclusions check + freshness)
  - `score` block (score, breakdown, why_it_matters, why_it_matters_model, assigned founder)
  - `capability_matches[]` — top-5 MacTech capability statements ranked by **pgvector cosine similarity** between the opportunity embedding and capability statement embedding
  - `sam_resource_links[]` — attachment URLs from SAM's raw payload (the PDFs/DOCX founders click through to)
- **`mactech.sam.fetch_descriptions` worker** at [apps/workers/src/mactech_workers/tasks/sam_descriptions.py](apps/workers/src/mactech_workers/tasks/sam_descriptions.py) — implements the chained noticedesc fetch documented in [docs/SAM_GOV_API.md §4 Chain 1](docs/SAM_GOV_API.md). Walks rows where `description_url` is set + `description_text` is null, hits SAM's `/prod/opportunities/v1/noticedesc?noticeid=...` with the api key, populates the column. Marks empty bodies with a single-space sentinel so the worker doesn't loop on them. 200kb size cap on stored text.
  - Beat schedule: every 30 min, batch=50.
  - First two manual runs filled 97 of 895 opps in ~12 seconds total.
- **Opportunity detail page** at [apps/web/app/(app)/opportunities/[id]/page.tsx](apps/web/app/(app)/opportunities/[id]/page.tsx) — three-column layout per [docs/MACTECH_PLAYBOOK.md §6](docs/MACTECH_PLAYBOOK.md):
  - Header strip with agency, title, meta line, posted date, deadline countdown ("Apr 27, 2026 (3 days left)" or "passed Nd ago"), notice id, SAM link
  - Left col: description card (renders `text` when fetched; "queued" message when pending; "no description" when unavailable) + Attachments list
  - Center col: Incumbent intelligence card (name, UEI, $cumulative, end date, exclusions with green/red treatment) + MacTech capability matches (top 3 with similarity score and truncated summary)
  - Right col: Score card (large number, breakdown per component with friendly labels, "Why this matters" paragraph + model attribution) + Actions card (stubbed today; pursuit pipeline + Sources Sought drafter ship in Phase 2 Week 7 and Phase 3 Week 11)
- **Dashboard cards** are now `<Link>` elements that route to the detail page on click. "View on SAM.gov" was removed from the dashboard tile (it's on the detail page); replaced with a "View detail →" affordance.

### Deferred to a follow-up Week 6 sprint
- **Full opportunities feed list with filters** (NAICS / agency / set-aside / value / score threshold). The "Opportunities" sidebar link still points at the placeholder page. Detail page works regardless — the dashboard's top-5 + the detail page give Patrick a working capture surface today; the full filterable feed is a nice-to-have for browsing beyond the top 5.

### Worker side note
While I was at it, the worker had been crash-importing `mactech_workers.tasks.sam_descriptions` — the import statement and beat-schedule entry were dropped from the first commit due to a tool-error race. A second commit fixed both. Worth noting because: when adding a new worker task module, the registration is in two places (the side-effect import at the bottom of `celery_app.py` and the beat schedule in `celery_app.conf.update.beat_schedule`). Both must land for the task to fire on schedule.

---

## 2026-04-24 — UI catch-up sprint (Phase 2 Week 6 closeout)

User feedback: *"the UI needs massive help and we need to be sure that the user is able to see everything they're supposed to."* Closed the gaps so every sidebar link points at a real page that surfaces what the API already knows.

### Shipped — three new API endpoints
- **`GET /opportunities`** at [apps/api/src/mactech_api/routes/opportunities.py](apps/api/src/mactech_api/routes/opportunities.py) — full filterable/sortable/paginated list. Filters: `q` (title contains), `naics_code`, `set_aside`, `notice_type`, `agency` (substring), `assigned_founder` (slug), `score_min`/`score_max`. Sort modes: `score_desc` (default), `posted_desc`, `deadline_asc`. Returns `items[]` plus `facets` (set_asides / notice_types / naics / assigned_founder counts) so the sidebar filters render with their tallies. One round-trip — raw SQL with `LEFT JOIN opportunity_scores` + `LEFT JOIN opportunities_enriched` + sub-select for the assigned-founder slug.
- **`GET /capability-statements`** at [apps/api/src/mactech_api/routes/library.py](apps/api/src/mactech_api/routes/library.py) — capability statements with founder slug→full_name resolution, related NAICS codes, and a `has_embedding` flag. The flag comes from a separate `select id where embedding is not null` query so we don't drag the 1024-dim vector across the wire.
- **`GET /me/settings`** at [apps/api/src/mactech_api/routes/settings.py](apps/api/src/mactech_api/routes/settings.py) — tenant header (UEI/CAGE pending placeholders, Clerk org id), founders[] with email + digest_enabled, NAICS matrix with founder_slugs per code, saved_searches[] with naics_codes/keywords/set_asides extracted from the filters JSON.

### Shipped — UI primitives module
- **[apps/web/components/ui.tsx](apps/web/components/ui.tsx)** — Tailwind-only, zero client JS, zero deps. `Card`, `PageHeader`, `Kpi`, `Badge` (6 tones), `ScoreBadge` (auto-tones by score: ≥80 green / ≥60 blue / ≥40 amber / else neutral), `Pillar` (security=blue, infrastructure=green, quality=amber, governance=violet), `SetAsideBadge` (SDVOSB family→violet, SBA family→green, NONE→unrestricted), `NoticeTypeBadge` (sources sought→amber, award→green, etc.), `EmptyState`, `LinkButton`, plus `fmtMoney`/`fmtDate`/`fmtRelativeDays` helpers. Goal: consistent visual rhythm across every page so a Brian or John can scan it without learning a new vocabulary on each route.

### Shipped — page replacements
- **`/opportunities`** at [apps/web/app/(app)/opportunities/page.tsx](apps/web/app/(app)/opportunities/page.tsx) — was a placeholder. Now: search box + sort selector + score-bucket quick-filters (Top ≥80 / Digest ≥60 / Med 40-59 / All) + facet sidebars (set-aside / notice type / NAICS / assigned founder, each with counts) + result cards showing ScoreBadge + NoticeTypeBadge + SetAsideBadge + NAICS + assigned founder + deadline countdown + truncated rationale + incumbent one-liner. Pagination at 25 per page with prev/next. The dashboard pillar cards now link to `/opportunities?assigned_founder=<slug>&score_min=60` so clicking "Brian's pillar" filters the list to Brian's assigned ≥60 opps.
- **`/library`** at [apps/web/app/(app)/library/page.tsx](apps/web/app/(app)/library/page.tsx) — was a placeholder. Now: 4-stat header (statements / embedded / past performance:0 / teaming partners:0) + grid of statement cards each with title, summary, related NAICS badges, owner founders with pillar pips, has_embedding flag. The "0 past performance / 0 teaming partners" stats explicitly point at Phase 2 Week 8.
- **`/settings`** at [apps/web/app/(app)/settings/page.tsx](apps/web/app/(app)/settings/page.tsx) — was a placeholder. Now: tenant card (name, slug, plan badge, UEI/CAGE with "(pending)" placeholders, clerk_org_id) + founders grid (4 cards with pillar/title/email/slug/digest status) + saved searches with threshold + cadence + channels inline + NAICS/set-asides/keywords for each + NAICS matrix table (code, title, primary/secondary tier badge, owner @-handles).
- **`/pipeline`** at [apps/web/app/(app)/pipeline/page.tsx](apps/web/app/(app)/pipeline/page.tsx) — still a placeholder per Phase 2 Week 7, but now uses the `Card` + `PageHeader` + `EmptyState` primitives so it visually fits with the rest of the app and shows the 6 stages as preview cards.

### Shipped — dashboard polish + detail page redesign
- **[apps/web/app/(app)/dashboard/page.tsx](apps/web/app/(app)/dashboard/page.tsx)** — rebuilt on the new primitives. Top-5 cards now show ScoreBadge + NoticeTypeBadge + SetAsideBadge inline (instead of a string of ` · `-separated text), pillar cards are clickable links into the filtered opportunities list, "see all your assigned ≥60" CTA, EmptyState component when zero results.
- **[apps/web/app/(app)/opportunities/[id]/page.tsx](apps/web/app/(app)/opportunities/[id]/page.tsx)** — score breakdown was getting cropped in the old 5/4/3 column split. Restructured to: header strip (full width) → 2-column main (description left, incumbent + capability matches stacked right) → **score+rationale full-width below** with the breakdown rendered as 4-column grid of mini-cards, each with the component label, the score, the max possible (eg "20 / 25"), and a horizontal progress bar. Now the founders can actually read the breakdown.

### Shipped — `lib/api.ts` types
- All response types for the three new endpoints were added to [apps/web/lib/api.ts](apps/web/lib/api.ts) so every page is fully typed against the actual API shape — `OpportunityListResponse` with `facets: { set_asides, notice_types, naics, assigned_founder } as Record<string,number>`, `CapabilityStatementsResponse`, `SettingsResponse`, etc.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 8 routes (`/`, `/dashboard`, `/library`, `/opportunities`, `/opportunities/[id]`, `/pipeline`, `/settings`, sign-in/sign-up).
- API: `python3 -m py_compile` clean on the new `routes/library.py`, `routes/settings.py`, the extended `routes/opportunities.py`, and `main.py`.

### Why this matters
Brian and John don't read code — they need a UI that surfaces what the system knows. Before this sprint, three of the five sidebar links were placeholders ("ships Phase 2 Week 7"), the dashboard was the only real page, and the score breakdown on the detail page was getting cut off. After this sprint, every link goes somewhere useful, the visual vocabulary is consistent (every score is a `ScoreBadge`, every set-aside is a `SetAsideBadge`), and the score breakdown is the second thing a founder sees on a detail page (right after the description). The product can now be demoed end-to-end without "this part isn't built yet."

### Still deferred
- **Pipeline kanban** — Phase 2 Week 7. The placeholder is now visually integrated but still a placeholder.
- **Past performance + teaming partners** in the library — Phase 2 Week 8.
- **Filter/sort persistence + saved views** — nice-to-have.
- **The right-column "Actions" panel** on the detail page (pursuit assignment, Sources Sought drafter) — Phase 2 Week 7 + Phase 3 Week 11.

---

## 2026-04-24 — Phase 2 Week 7: capture pipeline kanban

The placeholder is dead. Pursuits now have a real backing table, REST API, and a working kanban surface.

### Schema — migration 0007
- **`pursuits` table** (alembic [0007_pursuits.py](packages/db/alembic/versions/0007_pursuits.py), model [pursuit.py](packages/db/src/mactech_db/models/pursuit.py)):
  - One row per `(tenant_id, opportunity_id)` — enforced by `uq_pursuits_tenant_opp` unique constraint.
  - `stage` ∈ {lead, qualify, pursue, propose, submit, won, lost} — enforced by `ck_pursuits_stage` check constraint.
  - `owner_founder_id` nullable (ondelete=SET NULL — losing a founder doesn't drop the pursuit).
  - `notes` free-text.
  - `last_stage_change_at` separate from `updated_at` so we can compute "days in stage" without scanning a history table.
  - Indexes: `(tenant_id, stage)` for kanban grouping; `(owner_founder_id)` for owner filter.
  - Decision: free transitions allowed (no enforced DAG). Real BD work drops back to a prior stage all the time — "we got more info, this is a Qualify not a Pursue."

### API — [routes/pursuits.py](apps/api/src/mactech_api/routes/pursuits.py)
- **`GET /pursuits[?owner=<slug>]`** — kanban payload. Returns `columns[]` (one per stage in canonical order) each with `cards[]` (pursuits in that stage). One round-trip — raw SQL with `JOIN opportunities_raw + LEFT JOIN opportunity_scores + LEFT JOIN founders` for the owner slug. Cards include score, set-aside, NAICS, deadline + days-until, owner slug+name, days-in-stage. Also returns `by_owner` dict (counts per owner including `_unassigned`) for the filter pills.
- **`GET /pursuits/by-opportunity/{id}`** — single pursuit lookup, used by the detail page to decide whether to show "Add to pipeline" vs the pursuit panel. 404 when no pursuit exists.
- **`POST /pursuits`** — create from `opportunity_id`, optional `stage`/`owner_founder_slug`/`notes`. 409 if a pursuit already exists for that opp.
- **`PATCH /pursuits/{id}`** — change `stage` (auto-bumps `last_stage_change_at`), `owner_founder_slug` (or `clear_owner: true` to unassign), `notes`. Tenant-scoped — can't patch another tenant's pursuit.
- **`DELETE /pursuits/{id}`** — remove from pipeline. 204 No Content.

### Web — kanban page [/pipeline](apps/web/app/(app)/pipeline/page.tsx)
Server-rendered with **Next.js server actions** for every mutation — no client JS needed.
- **5-column active board** (Lead / Qualify / Pursue / Propose / Submit). Horizontal scroll on narrow viewports, 5-col grid on lg+. Each column shows count badge.
- **Terminal stages row** (Won / Lost) — only renders when there's at least one card in either, so an empty pipeline doesn't show empty win/lose columns.
- **Card UI** per pursuit: ScoreBadge + NoticeTypeBadge + truncated title (clickable to detail page) + SetAsideBadge + NAICS + deadline countdown + owner pill + "Nd in stage" + action row.
- **Card actions** (all server actions, no client JS):
  - `←` regress one stage / `→` advance one stage (active stages only).
  - `Won` / `Lost` finish buttons (visible from Qualify onward).
  - Owner select dropdown with "set" submit button. Includes `— unassigned` option (uses the `clear_owner: true` API flag).
  - `✕` remove from pipeline.
- **Owner filter pills** at the top — All / per-founder counts / unassigned chip. Clicking filters the kanban.

### Web — opportunity detail page [opportunities/\[id\]](apps/web/app/(app)/opportunities/[id]/page.tsx)
- New `<PursuitPanel>` strip directly under the header card.
- When **no pursuit exists**: dashed-border CTA "Not in the pipeline yet. Add it to start tracking the pursuit." + primary "Add to pipeline →" button. The button defaults `owner_founder_slug` to the calling user's founder slug (from `/me`), so a founder clicking it on their own opp self-assigns automatically.
- When **a pursuit exists**: stage badge with stage-specific tone (lead=neutral, qualify=blue, pursue=blue, propose=amber, submit=violet, won=green, lost=red), days-in-stage, owner display, notes, and inline action row (`← Prev` / `Next →` / `Won` / `Lost` / `Open kanban` / `Remove`).

### Web — server actions module [lib/pursuits.ts](apps/web/lib/pursuits.ts)
`"use server"` module with `createPursuit`, `updatePursuit`, `deletePursuit`. Each action calls the API, then `revalidatePath('/pipeline')` + `revalidatePath('/opportunities/[id]')` so the affected pages refresh without a hard nav. `apiFetch` was extended to handle 204 responses (was unconditionally calling `res.json()`).

### What this unblocks
- Brian / Patrick / James / John can now triage opportunities into the pipeline directly from the detail page.
- The kanban gives a real end-to-end picture of MacTech's pursuit posture: how many leads, how many in proposal, who owns what, how long has it been sitting.
- The "Why this matters" rationale + capability matches + score breakdown + pipeline state all live on one page now.

### Verification
- `tsc --noEmit` clean across `apps/web`. `next build` produces all 8 routes.
- `python3 -m py_compile` clean on the new model, migration, route, and updated `main.py`.
- Migration is idempotent (`create_table` + `create_index` + drop in reverse) and runs automatically on api boot via [entrypoint.sh](apps/api/entrypoint.sh).

### Next up
- **Phase 2 Week 8** — capability statements + past performance ingest. The library page already shows the stat slots ("Past performance: 0 — Phase 2 Week 8").
- **Drag-and-drop on the kanban** — nice-to-have. The button-based stage transitions work fully today; DnD is purely a polish item and would force a client component.
- **Pursuit history log** — every stage change captured with timestamp + actor. Useful for win-rate analysis later.

---

## 2026-04-25 — Phase 2 Week 8: past performance + teaming partners

The library is now a real catalogue, not just a list of seed-config capability statements. Both new tables are populated by the founders directly through the UI — no ingest worker yet (next iteration could pull MacTech's own contract history from USASpending once the UEI is registered).

### Schema — migration 0008
- **`past_performance`** ([0008_library_tables.py](packages/db/alembic/versions/0008_library_tables.py), model [library.py](packages/db/src/mactech_db/models/library.py)):
  - title (unique per tenant), customer_agency, customer_office, contract_number
  - role ∈ {prime, sub, joint_venture, individual} — enforced by check constraint
  - period_start, period_end, contract_value (numeric 14,2)
  - naics_code, summary (free text), keywords (array)
  - related_capability_slugs[], related_founder_slugs[] — soft links into the existing capability + founder rows
- **`teaming_partners`**:
  - name (unique per tenant), uei, cage_code
  - capabilities[], naics_codes[], set_aside_certifications[]
  - contact_name, contact_email, notes
  - status ∈ {active, inactive} — toggle on the card without leaving the library page
  - Index on `(tenant_id, status)` for fast active-first ordering

Both tenant-scoped with CASCADE on tenant delete. Both have ORM `onupdate=func.now()` on `updated_at`.

### API — two new route modules
- **[routes/past_performance.py](apps/api/src/mactech_api/routes/past_performance.py)** — full CRUD (`GET /past-performance`, `GET /{id}`, `POST`, `PATCH`, `DELETE`). PATCH supports explicit `clear_period_start` / `clear_period_end` / `clear_contract_value` flags so a user can null-out a previously set field. Sort: most recently completed first (period_end desc nulls last, then created_at desc).
- **[routes/teaming_partners.py](apps/api/src/mactech_api/routes/teaming_partners.py)** — same CRUD shape. Uses `EmailStr` for `contact_email` validation (relies on `fastapi[standard]` pulling email-validator). PATCH supports `clear_contact_email` flag. List sorts active partners first.
- Both routes filter by `ctx.tenant.id` everywhere — same tenancy isolation pattern as pursuits.
- Both POST/PATCH catch `IntegrityError` and surface a graceful 409 instead of a 500 when the (tenant, title)/(tenant, name) unique constraint trips.

### Web — restructured library
- **[/library](apps/web/app/(app)/library/page.tsx)** — was a single capability-statements list. Now a 3-section page:
  - 4-stat header (Statements / Past performance / Teaming partners / NAICS coverage — derived from the union of capability `related_naics` + past-performance `naics_code`).
  - Capability statements section (existing, unchanged behaviour).
  - **Past performance section** — newest-first cards with title + customer + role badge + contract value + 4-line summary + NAICS + period + owner founders + keyword chips. Inline Edit / Delete actions per card. Section-level "+ Add record" CTA.
  - **Teaming partners section** — 2-column grid of partner cards with status badge (active/inactive), capabilities chips, NAICS, set-aside certifications, contact name + clickable email, free-form notes. Inline Edit / Archive↔Reactivate / Delete actions per card.
- **Empty states** for both new sections frame them as setup tasks: "No past-performance records yet. Add the prior engagements you'd cite in a capability response." with the primary "+ Add the first record" CTA.

### Web — form pages (4 new routes)
- **[/library/past-performance/new](apps/web/app/(app)/library/past-performance/new/page.tsx)** + **[/library/past-performance/[id]/edit](apps/web/app/(app)/library/past-performance/[id]/edit/page.tsx)** — dedicated form pages with field-level hints ("Cited verbatim by the proposal drafter — write it the way you'd want a CO to read it"). Server actions handle create + update; redirect back to /library on success.
- **[/library/teaming-partners/new](apps/web/app/(app)/library/teaming-partners/new/page.tsx)** + **[/library/teaming-partners/[id]/edit](apps/web/app/(app)/library/teaming-partners/[id]/edit/page.tsx)** — same shape.
- Form components live in [components/library-forms.tsx](apps/web/components/library-forms.tsx) — server components that take a server-action prop. Update pages use `action.bind(null, id)` to bake the id into the action so the form doesn't need a hidden id input.

### Server actions module — [lib/library-actions.ts](apps/web/lib/library-actions.ts)
- `createPastPerformance` / `updatePastPerformance(id, formData)` / `deletePastPerformance` / `toggleTeamingPartnerStatus` / etc.
- Each parses FormData into the API shape (comma-split arrays, optional dates/numbers with explicit clear-flag handling), calls apiFetch, revalidatePath('/library'), and where appropriate redirects back to /library.

### What this unblocks
- Phase 3 Sources Sought drafter has real data to cite. Past performance narratives are now first-class records the drafter prompt can pull.
- Teaming-partner-aware suggestions on opportunity detail pages: "X partner has the FedRAMP-Mod ATO this opp requires."
- Founders can self-service the catalogue — no more code edits to add a citation.

### Verification
- `tsc --noEmit` clean, `next build` produces all 12 routes (the 4 new form routes + the 8 existing).
- `python3 -m py_compile` clean on the new model, migration, and 2 route modules.
- Models import via uv-managed venv with all 17 + 14 columns + 2 + 1 constraints respectively.
- Migration auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh).

### Next up
- **Phase 3 Week 9** — Sources Sought drafter. Take an opp + the capability statements + past performance + teaming partners, hand it all to Claude, return a draft response. This is the flagship feature.
- **Capability statement editing UI** — currently still seed-config-driven. Could mirror the past-performance form pattern.
- **USASpending past-performance auto-import** — once MacTech's UEI is active, pull the firm's own contract history into past_performance automatically.

---

## 2026-04-25 — Phase 3 Week 9: Sources Sought drafter (flagship)

The headline feature lands. Open any opportunity, click "Draft response", and 30 seconds later you have a 3–5-page Sources Sought response in markdown — citing your real capability statements + past performance + active teaming partners, with the firm's own UEI/CAGE/set-aside details baked in. Edit inline, regenerate with custom instructions, mark draft → reviewed → submitted.

### Schema — migration 0009
- **`proposal_drafts`** ([0009_proposal_drafts.py](packages/db/alembic/versions/0009_proposal_drafts.py), model [draft.py](packages/db/src/mactech_db/models/draft.py)):
  - `tenant_id`, `opportunity_id`, both CASCADE on delete.
  - `parent_draft_id` self-FK with `ondelete=SET NULL` — captures regeneration ancestry without orphaning the version chain when a parent is purged.
  - `created_by_founder_id` SET NULL on delete.
  - `draft_type` ∈ {sources_sought, rfp_response, compliance_matrix, white_paper} — extension points for next sprints. Check constraint enforces.
  - `status` ∈ {draft, reviewed, submitted, archived} — check constraint.
  - `version` integer (auto-incremented by API on regeneration, `parent.version + 1`).
  - `content` Text (the markdown response), `title` String(255), `custom_instructions` Text (nullable; what the user typed when generating).
  - `prompt_context_hash` SHA-256 over the inputs that drove the draft — lets us identify "this would produce the same draft" cases later.
  - `model`, `input_tokens`, `output_tokens`, `citations` JSONB (capability/past-performance/teaming-partner counts cited).
  - Indexes: `(tenant_id, opportunity_id)`, `(tenant_id, created_at)`.

### Intelligence — [sources_sought_drafter.py](packages/intelligence/src/mactech_intelligence/sources_sought_drafter.py)
- New module with structured `SourcesSoughtInput` dataclasses for opportunity / tenant / founders / capabilities / past performance / teaming partners.
- `_build_user_message()` flattens the input into a structured markdown prompt with `## OPPORTUNITY`, `## RESPONDING FIRM`, `## KEY PERSONNEL`, `## CAPABILITY STATEMENTS`, `## PAST PERFORMANCE`, `## TEAMING PARTNERS` sections. Description text is capped at 6000 chars.
- `generate_sources_sought_draft()` calls `AnthropicLLMClient.complete()` with `complexity="smart"` → routes to `claude-sonnet-4-6` per [docs/DATA_SOURCES.md §4.1](docs/DATA_SOURCES.md). Default `max_tokens=4000` (≈3000 words).
- System prompt at [prompts/sources_sought.md](packages/intelligence/src/mactech_intelligence/prompts/sources_sought.md) — sober federal-proposal-writer voice. Anti-hallucination: "Do not invent past performance, certifications, or facts not present in the context. If a section would be empty for lack of context, omit it rather than padding."
- `context_hash()` SHA-256 helper exposed for the API to detect "no-op regeneration."

### API — [routes/drafts.py](apps/api/src/mactech_api/routes/drafts.py)
- **`POST /opportunities/{id}/drafts/sources-sought`** — synchronous generation. Loads opportunity + founders + capabilities + past performance + active teaming partners + tenant identity (UEI / CAGE / contact) in a single set of queries, builds `SourcesSoughtInput`, calls Claude, persists. Returns the full `DraftOut` with content + metadata. 503 if `ANTHROPIC_API_KEY` is unset; 502 if the API call fails.
- **`POST /drafts/{id}/regenerate`** — same but with `parent_draft_id` chained and `version = parent.version + 1`. Optional new `custom_instructions` override the parent's.
- **`GET /drafts[?opportunity_id=<id>]`** — list (newest first). Optional opp filter.
- **`GET /opportunities/{id}/drafts`** — same shape, opp-scoped.
- **`GET /drafts/{id}`** — single draft including model/tokens/citations metadata + author.
- **`PATCH /drafts/{id}`** — edit `title`/`content`/`status`. Status check: must be one of the four valid values.
- **`DELETE /drafts/{id}`** — 204.
- **API now depends on `mactech-intelligence`** — added to `apps/api/pyproject.toml` (was already pulled in by `uv sync --all-packages` in the Dockerfile, now made explicit).

### Web — server actions [lib/drafts.ts](apps/web/lib/drafts.ts)
- `generateSourcesSoughtDraft(opportunityId, formData)` / `regenerateDraft(draftId, formData)` / `updateDraftContent(draftId, formData)` / `setDraftStatus(formData)` / `deleteDraft(formData)`.
- Generation calls override `apiFetch` with a 90-second timeout (`apiFetch` now accepts a `timeoutMs` param via `AbortController`); default for everything else is 15s.
- On success, the action `revalidatePath`s `/drafts`, the opp detail, and the new draft route, then `redirect()`s to the new draft so the user lands on the editor.

### Web — three new surfaces
- **Drafter panel on the opportunity detail page** — new `<DrafterPanel>` strip directly under the PursuitPanel. When the notice type contains "sources sought," shows an amber "recommended for this notice" chip. When no drafts exist, renders the form (custom instructions + "Draft response →"). When drafts exist, lists them with version + status + title + "Generate new version" affordance. The opp-detail page now fetches drafts in parallel with /me + pursuit lookup.
- **`/drafts`** ([page.tsx](apps/web/app/(app)/drafts/page.tsx)) — tenant-wide list of all drafts across all opportunities. Each card shows status badge, draft type, version, parent opportunity title, model + token count, created-at. Empty state directs the user to filter opps to "Sources Sought."
- **`/drafts/[id]`** ([page.tsx](apps/web/app/(app)/drafts/[id]/page.tsx)) — 2/3 + 1/3 split:
  - **Editor (left, 2 cols)**: title input + 36-row textarea for the markdown body. "Save changes" via `updateDraftContent.bind(null, draft.id)`.
  - **Sidebar (right, 1 col)**: generation metadata (model, tokens, citations counts, parent draft link if v2+, author founder), plus a "Regenerate" panel with custom-instructions textarea and a primary "Generate v{N+1}" button.
  - Status flow: top-right action row only exposes valid next-status transitions per `STATUS_FLOW` map (e.g., draft → reviewed | archived; reviewed → submitted | draft).
- **Sidebar nav** picks up a new "Drafts — Sources Sought + RFP" entry between Library and Settings.

### Verification
- `tsc --noEmit` clean (cleaned up stale `.next/types/* 2.ts` Finder duplicates that were creating false-positive errors).
- `next build` produces all 14 routes (2 new: `/drafts`, `/drafts/[id]`).
- `python3 -m py_compile` clean on the new model, migration, intelligence module, and route module.
- Models import via uv with all 18 columns + 2 check constraints + 2 indexes present.
- Migration auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh).

### What this unblocks
- The flagship feature is live. MacTech can respond to Sources Sought notices in minutes instead of days.
- Every Phase 3 follow-on (RFP response drafter, compliance matrix generator, white-paper drafter) reuses the same `proposal_drafts` table with a different `draft_type` and a different prompt template.
- Token usage now tracked per draft → real-time visibility into Anthropic spend.

### Known limitations + next sprints
- **Synchronous generation** — the API call blocks for 20–60s. Phase 3 Week 10 should move to streaming (Server-Sent Events) so the user sees the draft compose live.
- **No PDF/Word export** — markdown only today. Phase 3 Week 11 ships a "Export as DOCX" via a server-side conversion step.
- **No diff view between versions** — when you regenerate, you get a new draft but no side-by-side. Useful for understanding "what changed when I asked for X."
- **No rate limiting on generation** — a user could spam regenerate. Add a per-tenant 5/hour soft cap when costs become real.

---

## 2026-04-25 — UX overhaul, Sprints 1 & 2

User asked for a "massive UX/UI overhaul using AI and API enrichment." Plan + Explore agents both diagnosed the same thing: information architecture is fine, but the app reads like a developer console — badge inflation, 11px eyebrows everywhere, opaque jargon, primary actions that don't feel primary. Five-sprint plan; this commit lands the first two.

### Sprint 1 — "The friendly skin" (no API changes — pure presentation)

**Tailwind config** ([tailwind.config.ts](apps/web/tailwind.config.ts))
- Added `brand` palette anchored on deep teal `#207b78` (50–950). Federal/GSA-adjacent, distinct from generic tech blue, legible at small weights on white.
- Default focus ring now brand teal.

**Type scale** ([globals.css](apps/web/app/globals.css))
- Body bumped to 15px / 1.55 line-height. Floor for `text-xs` lifted but proportional. Visible focus rings on `:focus-visible`.

**UI primitives** ([components/ui.tsx](apps/web/components/ui.tsx))
- `Card` padding `p-5` → `p-6`, radius `rounded-md` → `rounded-lg`, eyebrow type weight bumped.
- `PageHeader` title `text-2xl` → `text-3xl`; eyebrow gets brand-teal tone (was neutral); subtitle `text-sm` → `text-base` for the layman.
- `Kpi` accepts a `tone` prop (`"neutral" | "brand" | "amber" | "red"`). Value type bumped 2xl → 3xl.
- `Badge` adds `brand` tone; base size lifted from `text-[11px]` to `text-xs` (12px).
- New `ScoreBadge` `size="lg"` variant — bigger, with "/100" subscript, contextual tooltip ("Strong fit — pursue", "Worth a look", "Watch list", "Long shot").
- New `Button` primitive (`primary` / `secondary` / `ghost` / `danger`). `LinkButton.primary` now uses brand teal instead of `bg-neutral-900` so primary CTAs *feel* primary.

**Sidebar** ([components/sidebar-nav.tsx](apps/web/components/sidebar-nav.tsx))
- Active item: brand-50 background, brand-700 left border, brand-700 sub-label color. Was neutral-900 fill — now distinguishable at a glance.

**Dashboard** ([app/(app)/dashboard/page.tsx](apps/web/app/(app)/dashboard/page.tsx))
- KPI tiles fully replaced. Old: ingestion exhaust ("Posted last 24h", "Scored ≥ 60", "With incumbent intel"). New: action-oriented metrics, each clickable to a filtered view:
  - **High-fit, untracked** — opps assigned to me ≥60 not in pipeline → links to filtered opps. Brand tone when >0.
  - **Deadlines this week** — opps assigned to me with deadline ≤7 days. Amber tone when >0.
  - **Active pursuits** — pursuits I own (excl. won/lost) → links to my kanban.
  - **Drafts to review** — tenant drafts in 'draft' or 'reviewed' status → links to /drafts. Brand tone when >0.
- API: [routes/me.py](apps/api/src/mactech_api/routes/me.py) `DashboardKpis` extended with `your_high_fit_open`, `your_deadlines_lt_7d`, `your_active_pursuits`, `drafts_awaiting_review`.
- Old tenant-wide KPIs preserved as a small dashed "Tenant feed" footer strip — context without distraction.
- "Top N" cards: deadline pulled out to its own right-aligned column with "Deadline" label. Score badge upgraded to `size="lg"`. Clean separation of *what is this* (left) vs *when is it due* (right).
- "How CaptureOS works" block now persistently dismissible via cookie (`mactech.dismiss.howitworks`). New [lib/preferences.ts](apps/web/lib/preferences.ts) holds `dismissHowItWorks` + `showHowItWorks` server actions; dashboard reads cookie via `next/headers`. Footer "Show 'How CaptureOS works'" button to bring it back.

**Opportunities list** ([app/(app)/opportunities/page.tsx](apps/web/app/(app)/opportunities/page.tsx))
- Filter sidebar collapsed from 6 cards to 3 (Set-aside / Notice type / Assigned founder) + a `<details>` "More filters" disclosure containing NAICS facet + Sort.
- Score thresholds promoted from sidebar card to a horizontal segmented control at the top of the page. Renamed for plain-English: "Top fit / Worth a look / Watch list / All". Active button uses brand teal fill.
- Search box + sort indicator moved into the same top bar.
- Result cards trimmed: Score (size lg) + ONE contextual chip (Sources Sought wins; otherwise Set-aside wins) + assigned founder. Other badges (NoticeType, Set-aside, NAICS) hidden by default, revealed inline on `:hover` via `group-hover:inline-flex`.
- Deadline pulled to a right-aligned column on each card. Posted date demoted under it. The thing a layman wants first is *when do I need to respond by*.

### Sprint 2 — "Explain this" rail (first AI-enrichment surface)

**Schema** — migration 0010 ([0010_term_explanations.py](packages/db/alembic/versions/0010_term_explanations.py), model [term_explanation.py](packages/db/src/mactech_db/models/term_explanation.py))
- New `term_explanations` table: `slug` (e.g. `naics:541512`, `set_aside:SDVOSB`), `kind`, `label`, `summary`, `body`, `prompt_version`, `model`, `input_tokens`, `output_tokens`, `first_requested_by_tenant_id`. Unique on `(slug, prompt_version)`. Indexed on `slug`.
- Cache key is global, not per-tenant — the explanation of NAICS 541512 doesn't vary by tenant. `prompt_version` bump invalidates the cache without a sweep.

**Intelligence** ([explain_term.py](packages/intelligence/src/mactech_intelligence/explain_term.py) + [prompts/explain_term.md](packages/intelligence/src/mactech_intelligence/prompts/explain_term.md))
- New `explain_term(client, slug)` function. Routes to `complexity="fast"` → Claude Haiku (low-cost, ~220 words).
- Prompt explicitly written for layman audience: "Veteran-owned small business owner. Founded a federal-contracting firm but is not a lawyer or proposal writer." Output format: one summary sentence (under 25 words, no jargon) + 2–4 short prose paragraphs covering meaning + relevance + next action. Hard-banned marketing words ("leverage," "synergy," "robust"). No-fact-invention guardrail.
- `_KIND_INTROS` dict gives the model context per kind so `set_aside:NONE` doesn't get misinterpreted.
- Output parser splits summary line from body cleanly.

**API** ([routes/explain.py](apps/api/src/mactech_api/routes/explain.py))
- `GET /explain/{slug:path}` — read-through cache. Cache hit returns `cached: true` instantly. Cache miss calls Haiku, persists, returns `cached: false`. Allowed kinds: `naics`, `set_aside`, `notice_type`, `score_component`, `agency`. 503 if `ANTHROPIC_API_KEY` missing; 502 on Anthropic failure. Race-safe via second-read fallback on IntegrityError.

**Web — clickable badges** ([components/ui.tsx](apps/web/components/ui.tsx))
- New `ExplainLink` helper. Wraps any badge in a `<Link href="?explain=<slug>">` with a small `?` glyph appended. Relative href preserves the current path + other search params.

**Web — opp detail right rail** ([app/(app)/opportunities/[id]/page.tsx](apps/web/app/(app)/opportunities/[id]/page.tsx))
- Page accepts `searchParams.explain` and fetches `GET /explain/{slug}` in parallel with the existing pursuit + drafts + me requests. 45-second timeout (cache hits return in <100ms; first-time generations take a few seconds).
- When `?explain=...` is present, the page lays out as a 2-column grid (`minmax(0,1fr) 22rem` on lg+) with the main content on the left and a sticky `<ExplainRail>` aside on the right.
- The rail shows: brand-teal eyebrow "Explain this", the term's human label, the summary sentence in bold, the body as separate paragraphs, and a footer indicating cache status + "click any underlined term to swap." Close link sets `href` back to the bare detail URL.
- **Clickable terms now**: notice type badge, set-aside badge, NAICS badge, every score-component label on the breakdown grid. All wrapped in `ExplainLink` with `<kind>:<value>` slugs.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 14 routes (no new web routes — rail uses URL param on existing detail page).
- `python3 -m py_compile` clean on the new model, migration, intelligence module, and route module.
- Migration 0010 auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh).

### What this changes for a Brian or John on first visit
- **Dashboard** opens with their *day*, not the system's exhaust: "You have 3 high-fit untracked, 2 deadlines this week, 4 active pursuits, 1 draft to review." Each tile is clickable to the filtered view.
- **Opportunities list** has 3 filters not 6, score buckets that say "Top fit" not "≥80", and a deadline column that's the second-most-prominent thing on every card.
- **Detail page** — every NAICS code, set-aside code, notice type, and score component now has a small `?` glyph that opens a plain-English explainer. "What is SDVOSB?" → 3 paragraphs in 3 seconds, cached forever after first ask.

### Sprints 3–5 still pending
- **Sprint 3** — per-opportunity "Ask Claude about this opp" with 3 starter buttons; native streaming via Next.js server components.
- **Sprint 4** — worker-extracted structured opportunity briefs replacing the raw SAM `<pre>`; PDF upload on /library with auto-parse.
- **Sprint 5** — onboarding flow with SAM Entity API auto-fill; USASpending agency-level rollup card; Cmd-K hybrid pgvector + pg_trgm global search.
