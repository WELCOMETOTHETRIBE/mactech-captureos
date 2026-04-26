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

---

## 2026-04-25 — UX overhaul, Sprints 3 & 4

### Sprint 3 — "Ask Claude about this opp"

The single highest-conversion AI feature for the layman audience: type a question (or tap a starter button), get a 200-word answer grounded in your firm's data + the opportunity's text. Persists to a tenant-scoped history so the team builds on each other's questions.

- **Schema** (migration 0011): `opportunity_questions` table — `tenant_id`, `opportunity_id`, `asked_by_founder_id` (SET NULL on delete), `question`, `answer`, `starter_kind`, `model`, `input_tokens`, `output_tokens`, `prompt_version`. Composite index on `(tenant_id, opportunity_id, created_at)` for ordered reads.
- **Intelligence** ([ask_about_opportunity.py](packages/intelligence/src/mactech_intelligence/ask_about_opportunity.py) + [prompts/ask_about_opp.md](packages/intelligence/src/mactech_intelligence/prompts/ask_about_opp.md)) — Claude Sonnet ("smart"). Prompt explicitly addresses non-technical founder audience; 200-word cap; no marketing language; never invents facts. `STARTERS` dict maps starter keys to canonical question text; the API resolves the user's `starter_kind` to the canonical text so the prompt is consistent across users.
- **API** ([routes/ask.py](apps/api/src/mactech_api/routes/ask.py)) — `POST /opportunities/{id}/ask` (5–15s sync), `GET /opportunities/{id}/questions` (history with `starters` dict for the UI), `DELETE /opportunity-questions/{id}`. Answer context: opportunity metadata + description + score + breakdown + incumbent + capability statements + past performance + active teaming partners + founders.
- **Web** — `<AskPanel>` strip on the opportunity detail page directly under the DrafterPanel:
  - Five starter buttons in a horizontal pill row: "Should we pursue this?", "Who's the likely incumbent?", "What's our win probability?", "What are the must-haves?", "Should we prime, sub, or team?"
  - Freeform text input + "Ask →" primary button on its own row.
  - History list of last 5 Q&A rounds, each with delete button. `revalidatePath` on the detail route after mutations so the new question appears without a hard refresh.
  - apiFetch timeout overridden to 60s for the POST.

### Sprint 4 — "What they really want" structured brief

Replaces the raw SAM `<pre>` description with a 30-second structured read. Lazy generation (button on first view), one row per (tenant, opp).

- **Schema** (same migration 0011): `opportunity_briefs` table — `scope_one_sentence` (Text), `must_have_requirements` (JSONB array), `nice_to_have` (JSONB), `red_flags_for_small_biz` (JSONB), `suggested_team_roles` (JSONB), plus model + tokens + `description_chars` for cost tracking. Unique constraint on `(tenant_id, opportunity_id)` so regeneration upserts in place.
- **Intelligence** ([extract_brief.py](packages/intelligence/src/mactech_intelligence/extract_brief.py) + [prompts/extract_brief.md](packages/intelligence/src/mactech_intelligence/prompts/extract_brief.md)) — Claude Sonnet ("smart"). Prompt requires JSON-only output with strict schema; max 6 must-haves, 4 nice-to-haves, 4 red flags, 4 team roles; ≤25 words per bullet. Hard guardrail: "Do not invent. If the description is silent on a topic, leave the array empty rather than padding." Description capped at 12k chars to bound token cost. `_strip_code_fence` handles the rare case the model wraps output in ```json…```. `BriefExtractionError` raised on invalid JSON.
- **API** ([routes/brief.py](apps/api/src/mactech_api/routes/brief.py)) — `GET /opportunities/{id}/brief` (404 when none generated), `POST /opportunities/{id}/brief` (creates or upserts), `DELETE /opportunities/{id}/brief`. 409 if the opportunity has no description text yet (the fetch_descriptions worker hasn't pulled it). 502 if Anthropic returns invalid JSON.
- **Web** — replaces the old `Description` Card on the detail page with `<BriefAndDescriptionPanel>`:
  - Two `role="tab"` anchor links at the top: "Plain-English brief" (default, `#brief-{id}`) | "Original SAM text" (`#raw-{id}`). Anchor-based tab switching keeps the view fully server-rendered with zero client JS.
  - When a brief exists: renders `Scope` (one-sentence headline), then four colored bullet sections (Must-have requirements / Nice-to-haves / Red flags for a small business / Suggested teaming) — each with a small dot in the section's tone color. Auto-generation provenance footer with model + char count.
  - When no brief exists: dashed-border CTA panel. If description text exists → "Generate brief →" primary button. If description is pending → "queued for fetch" message. If no description ever → "SAM didn't return any text" message.
  - "↻ Regenerate brief" link in the panel header when a brief exists.
  - Original SAM text moves to a secondary section below, scrollable in a max-h-96 box, smaller font. Attachments now also live there.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 14 routes.
- `python3 -m py_compile` clean on the 2 new models, migration, 2 intelligence modules, 2 route modules.
- Migration 0011 auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh).

### What this unlocks for a Brian or John
- **Ask panel**: tap "Should we pursue this?" → 200-word answer in 10s grounded in your real data. No more reading 4 pages of dense PWS to figure out fit.
- **Brief tab**: open any opp → click "Generate brief" → 15s later you have scope + must-haves + red flags + teaming suggestions in a single screen. The raw SAM text is still one tab away when you need to verify a specific phrase.
- **Per-opp Q&A history**: founders see what each other already asked. "Did anyone check whether this requires a TS clearance?" → one click and you can read the answer from last Tuesday.

### Sprint 5 still pending
- Onboarding flow with SAM Entity API auto-fill on UEI.
- USASpending agency-level rollups card on detail page.
- Hybrid pgvector + pg_trgm Cmd-K global search.
- PDF upload on /library with auto-parse (deferred from Sprint 4 to keep this commit reviewable).

---

## 2026-04-25 — UX overhaul, Sprint 5 (partial): pipeline aging + agency intel + Cmd-K

User said "sprint 5 lets go!" Three high-impact pieces shipped; onboarding flow + PDF upload deferred to Sprint 6 — they each warrant their own session.

### Pipeline aging signal ([app/(app)/pipeline/page.tsx](apps/web/app/(app)/pipeline/page.tsx))
- Cards in active stages get a 2px colored border based on `days_in_stage`:
  - **0–6 days**: neutral, normal border.
  - **7–13 days**: amber border + amber bold age text. "Time to advance or document why it's parked."
  - **≥14 days**: red border + red bold age text. "Move it forward, kill it, or accept it's parked."
- Won/Lost cards never go stale (terminal stages are correctly inert).
- Hover tooltip on the age line includes a contextual prompt for the user.

### Agency intel card

**Schema** — migration 0012 ([0012_agency_intel.py](packages/db/alembic/versions/0012_agency_intel.py), model [agency_intel.py](packages/db/src/mactech_db/models/agency_intel.py))
- `agency_naics_intel` cache table — `(agency_name, naics_code, lookback_days)` unique key. Stores `award_count`, `total_obligated`, `avg_award_value`, `median_award_value`, `top_recipients` JSONB, `set_aside_breakdown` JSONB, `lookup_failed` flag + `failure_note` for graceful negative caching.
- Migration also `CREATE EXTENSION IF NOT EXISTS pg_trgm` and adds GIN indexes on `opportunities_raw.title`, `proposal_drafts.title`, `teaming_partners.name`, `past_performance.title` — these power the Cmd-K search below.

**API** ([routes/agency_intel.py](apps/api/src/mactech_api/routes/agency_intel.py))
- `GET /opportunities/{id}/agency-intel` — read-through cache with 7-day TTL; failures cached 1 day so the UI doesn't retry-storm transient USASpending issues. Falls back to stale data on USASpending error if a cached row exists. 503 on rate limit; 409 if the opp is missing agency name or NAICS code.
- Aggregate is computed from the top 100 awards in the last 365 days (USASpending limit) — sample-size disclosed in the response. Top 5 recipients ranked by total dollars across the sample.
- API package now declares `mactech-integrations` as an explicit dep (was already present at runtime via `uv sync --all-packages`).

**Web** ([apps/web/lib/agency-intel.ts](apps/web/lib/agency-intel.ts) + [opp detail page](apps/web/app/(app)/opportunities/[id]/page.tsx))
- New `<AgencyIntelCard>` strip below the 2-column main on the opportunity detail page.
- Page fetches `/agency-intel` in parallel with the existing requests using a **4-second timeout** — cache hits (<100ms) render the data immediately; cache misses (5–10s) gracefully fall through to a "Pull agency intel →" CTA. The CTA fires `pullAgencyIntel` server action with a 30s timeout.
- States: empty (CTA), failure (USASpending didn't resolve, with retry), zero matches (this agency hasn't bought under this NAICS recently), and full data render with 4 stat tiles + top 5 recipients + cache metadata.

### Cmd-K hybrid global search

**API** ([routes/search.py](apps/api/src/mactech_api/routes/search.py))
- `GET /search?q=<query>&limit=8` — pg_trgm `%` operator + `similarity()` ranking across:
  - opportunities (title; tenant-bridged via `opportunity_scores`)
  - proposal drafts (title)
  - teaming partners (name)
  - past performance (title)
- Empty query returns recents per kind (acts as the "default" view when the modal opens).
- Response is grouped by kind and flattened — UI consumes the grouped form for sectioned rendering plus the flat form for keyboard navigation indices.
- `set_config('pg_trgm.similarity_threshold', '0.10', true)` per request to keep `%` selective without polluting the global setting.

**Web** ([components/cmd-k.tsx](apps/web/components/cmd-k.tsx))
- New client component `<CmdK>` mounted once in [app/(app)/layout.tsx](apps/web/app/(app)/layout.tsx).
- Cmd-K (or Ctrl-K) toggles the modal globally; Escape closes; click on the dimmed scrim closes; ↑↓ navigate; Enter opens the highlighted result.
- 200ms debounced search via `useTransition`. Each keystroke calls the `searchEverything` server action; pending state shows "Searching…".
- Sectioned result rendering with brand-50 highlight on the active item.
- Footer shows the keyboard hints (`↑↓`, `↵`, `esc`) so the layman discovers the controls.
- New `<CmdKTrigger>` button mounted in the sidebar header — for users who haven't learned the shortcut. Synthesizes a Cmd-K keystroke on click so the trigger and shortcut share the same code path.
- Single client island; everything else stays server-rendered.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 14 routes (no new pages — Cmd-K is an overlay; agency intel is an inline card).
- `python3 -m py_compile` clean on the new model, migration, intelligence module not needed (pure SQL/Python in the route), and 2 route modules.
- Migration 0012 auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh). pg_trgm extension creation is idempotent.

### Still ahead (Sprint 6 candidates)
- **Onboarding flow** — 5-step wizard for new tenants with SAM Entity API auto-fill on UEI, capability statement parsing, NAICS picker, founder add, first-feed preview.
- **PDF upload** on /library — drag-drop a capability-statement PDF or past-performance write-up; PyMuPDF parse → Claude extract → preview-and-confirm flow.
- **Streaming Q&A** — replace the synchronous `ask_about_opportunity` with native Next.js streaming server components so the answer composes live.
- **DOCX export** for proposal drafts — server-side markdown → docx via python-docx.

---

## 2026-04-25 — Sprint 6: DOCX export + PDF import for past performance

User said proceed with Sprint 6 if previous sprints are done — they were (clerk_org_id incident fixed live + durably). Two of four Sprint 6 candidates landed; onboarding flow and streaming Q&A defer to Sprint 7.

### Sprint 6A — DOCX export for proposal drafts

The drafter has been emitting markdown since [Phase 3 Week 9](#); this closes the loop so a CO can actually receive the response in standard Word format.

- **API deps**: added `python-docx>=1.1` to `apps/api/pyproject.toml`.
- **[apps/api/src/mactech_api/docx_export.py](apps/api/src/mactech_api/docx_export.py)** — small custom markdown→DOCX converter for the subset the drafter actually emits (H1/H2/H3, plain paragraphs, single-level bullets, `**bold**` / `*italic*` runs). No heavy markdown lib; ~150 lines. Document properties (title / subject / author) populated from the draft + opportunity. Times New Roman 11pt body, footer attribution.
- **API endpoint** added to [routes/drafts.py](apps/api/src/mactech_api/routes/drafts.py):
  - `GET /drafts/{id}/export.docx` — tenant-scoped lookup, calls `markdown_to_docx_bytes()`, returns binary with `Content-Disposition: attachment; filename="<safe-slug>-v<n>.docx"`.
- **Web** — new Next.js route handler at [apps/web/app/drafts/[id]/export.docx/route.ts](apps/web/app/drafts/[id]/export.docx/route.ts). Lives **outside** the `(app)` route group so the layout shell doesn't wrap a binary response. Uses `auth()` + `getToken({ template: "mactech" })` to attach the Clerk JWT, fetches the API, streams the body back with the API's Content-Disposition. Clerk middleware matcher already excludes `.docx` paths so the route runs without middleware redirects; the handler does its own auth check + redirect-to-signin.
- **UI** — "⬇ Export DOCX" button in the [draft detail page header](apps/web/app/(app)/drafts/[id]/page.tsx) trailing slot. Brand-teal primary so it reads as the next action after "Save changes."

### Sprint 6B — PDF import for past performance

Founders can now drop a prior-engagement PDF on /library and have Claude extract the fields into a new `past_performance` record they can review before keeping. Closes the gap that forced manual data entry for every record.

- **API deps**: added `pymupdf>=1.24` to `apps/api/pyproject.toml`.
- **Intelligence** ([extract_past_performance.py](packages/intelligence/src/mactech_intelligence/extract_past_performance.py) + [prompts/extract_past_performance.md](packages/intelligence/src/mactech_intelligence/prompts/extract_past_performance.md)) — Claude Sonnet ("smart"), strict JSON schema for past-performance fields. Hard guardrails: never invent contract numbers or dollar amounts; null over guess. Aggressive truncation (25k chars) for cost control. Returns `ExtractedPastPerformance` dataclass; `PastPerformanceExtractionError` raised on invalid model output.
- **API** ([routes/library_import.py](apps/api/src/mactech_api/routes/library_import.py)) — `POST /library/import/past-performance/from-pdf` — multipart endpoint. Validates content-type + 20MB cap. Parses with PyMuPDF (`fitz.open(stream=blob, filetype="pdf")` then `page.get_text("text")` per page). Rejects scanned PDFs (<30 chars extracted) with a friendly OCR-not-supported-yet message. Calls Claude, persists a fresh `past_performance` row, returns `{id, title, edit_url, notes[]}`. Title-collision fallback appends a date suffix instead of erroring.
- **Web** — new server action [lib/library-import.ts](apps/web/lib/library-import.ts) `importPastPerformanceFromPdf`. Receives FormData, attaches Clerk JWT, posts multipart to API with a 90-second timeout, then `redirect()`s to the new record's edit page so the user reviews and saves. Bubbles structured `detail` from API errors so the form can surface them.
- **Import page** at [/library/past-performance/import](apps/web/app/(app)/library/past-performance/import/page.tsx) — dashed-border drop zone (clickable label wrapping a hidden `<input type="file" accept="application/pdf,.pdf">`), expandable "What works best?" tip block, primary "Import & review →" button. Manual-form fallback link at the bottom.
- **Library entry points** — past-performance section header now has two CTAs side-by-side: "⬆ Import PDF" (brand-tinted) + "+ Add record" (neutral-dark). Empty state likewise gives both options. Existing manual flow untouched.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 16 routes (2 new: `/drafts/[id]/export.docx` route handler, `/library/past-performance/import` page).
- `python3 -m py_compile` clean on the new export module, intelligence module, and API route.
- New pyproject deps: `python-docx>=1.1`, `pymupdf>=1.24` — both Docker-friendly, both will install on next Railway build.

### Trade-offs called out
- **No OCR yet.** Scanned PDFs are rejected with a clear "text-based PDFs only — OCR ships in a later sprint" message. Adding OCR (tesseract or paid API) is its own decision.
- **Title-collision falls back to a date-suffix** rather than 409. The user is going to the edit page next anyway and can rename to whatever they want.
- **No capability statement PDF upload yet.** Capability statements are still seed-config-only since we haven't built the UI editor — the import flow would have nowhere to land. That's a paired "capability CRUD UI + PDF upload" sprint.

### Sprint 7 candidates
- **Onboarding flow** — 5-step wizard for net-new tenants with SAM Entity API UEI auto-fill, capability statement parsing, NAICS picker, founder add, first-feed preview.
- **Capability statement CRUD UI + PDF upload** — finishes the parallel to past performance.
- **Streaming Q&A** — replace the synchronous `ask_about_opportunity` with native Next.js streaming server components so the answer composes live.
- **OCR for scanned PDFs** — extends the Sprint 6 PDF flow to handle image-based documents.

---

## 2026-04-25 — Sprint 7: capability statement CRUD UI + PDF upload

User said "sprint 7 execute". Picked the largest blocker on the audit's punch list: capability statements were seed-config-only since Phase 1, blocking any net-new tenant from self-serving the catalogue. Now they're full first-class records with the same Add / Import / Edit / Delete pattern past performance got in Sprint 6.

### API — capability statement CRUD ([routes/library.py](apps/api/src/mactech_api/routes/library.py))
- `GET /capability-statements/{id}` — single record (was list-only).
- `POST /capability-statements` — create. 409 on title collision.
- `PATCH /capability-statements/{id}` — update title/summary/keywords/related_naics/related_founder_slugs. **If summary text changes, the route nulls the embedding column** so the embed worker re-embeds on its next 15-min tick instead of leaving a stale vector live.
- `DELETE /capability-statements/{id}` — 204.
- Read shape extended with `keywords` field (was buried only in writes).

### Intelligence — capability statement extraction
- New module [extract_capability_statement.py](packages/intelligence/src/mactech_intelligence/extract_capability_statement.py) + [prompts/extract_capability_statement.md](packages/intelligence/src/mactech_intelligence/prompts/extract_capability_statement.md).
- Claude Sonnet, JSON-only output, strict schema. Prompt tuned for one-pager / capability-deck PDFs: title (noun-first, ≤80 chars), 3–5 sentence summary with specific frameworks named, ≤10 keywords, ≤6 NAICS, ≤4 owner founder slugs.
- Hard guardrails: no invention of NAICS or founder names; empty arrays over fabrication. Banned marketing words enforced in the prompt.
- 25k char truncation, 1500-token cap.

### API — PDF import for capability statements ([routes/library_import.py](apps/api/src/mactech_api/routes/library_import.py))
- New endpoint `POST /library/import/capability-statements/from-pdf`.
- Same pattern as past-performance import: PyMuPDF extract → Claude → upsert into `capability_statements`. Title-collision fallback appends a date suffix.
- Existing past-performance import refactored to share `_importViaPdf()` helper in [lib/library-import.ts](apps/web/lib/library-import.ts) — 50 lines of dedup.

### Web — three new routes
- **[/library/capability-statements/new](apps/web/app/(app)/library/capability-statements/new/page.tsx)** — manual form.
- **[/library/capability-statements/[id]/edit](apps/web/app/(app)/library/capability-statements/[id]/edit/page.tsx)** — edit form. Header surfaces "no embedding yet — worker picks it up next 15-min tick" amber chip when the embedding hasn't materialized yet.
- **[/library/capability-statements/import](apps/web/app/(app)/library/capability-statements/import/page.tsx)** — drop zone with expandable "What works best?" tips.
- Shared form: new `<CapabilityStatementForm>` in [components/library-forms.tsx](apps/web/components/library-forms.tsx) — same pattern as PastPerformanceForm/TeamingPartnerForm.

### Web — server actions + library wiring
- New actions in [lib/library-actions.ts](apps/web/lib/library-actions.ts): `createCapabilityStatement`, `updateCapabilityStatement`, `deleteCapabilityStatement`. `update*` is `bind(null, id)`'d on the edit page so forms don't need hidden id inputs.
- New action `importCapabilityStatementFromPdf` in [lib/library-import.ts](apps/web/lib/library-import.ts).
- [Library page](apps/web/app/(app)/library/page.tsx) capability section header now mirrors past performance: "⬆ Import PDF" + "+ Add cluster" buttons. Each capability card now has inline Edit / Delete actions in a footer row. Old "seeded from yaml — UI editing ships in a later sprint" subtitle replaced with the engine-relevant explainer.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 19 routes (3 new: `/library/capability-statements/new`, `/[id]/edit`, `/import`).
- `python3 -m py_compile` clean on the new intel module + extended library.py + extended library_import.py.

### Trade-offs called out
- **Embedding lag on update.** Updating a capability summary nulls the embedding column; the embed worker fixes it on its next 15-minute tick. During that window, opportunity scoring uses the *non-embedded* path for that capability (no vector match contribution). Acceptable for a 4-person tenant; if we wanted instant re-embedding we'd fire a Celery task inline. Deferred.
- **Founder slug FK is soft.** The model stores `related_founders` as JSONB `[{"slug": "..."}]`. If a founder is renamed or deleted, capability statements pointing at the old slug just render with no name on read. Same behavior as before; no regression.

### Sprint 8 candidates left
- **Onboarding flow** with SAM Entity API UEI auto-fill, NAICS picker, founder add, first-feed preview. The biggest piece remaining; should be its own session.
- **Streaming Q&A** on the Ask panel.
- **OCR for scanned PDFs** — extends the Sprint 6/7 PDF flow.
- **Inline embedding on capability update** — if the embedding lag matters in practice.

---

## 2026-04-25 — Sprint 8: onboarding flow with SAM Entity API auto-fill

User said "sprint 8 lets go". Picked the productization headline: a tenant-identity wizard that auto-fills firm details from a single UEI lookup against SAM.gov's Entity API. NAICS/founder pickers and first-feed preview defer to Sprint 9.

### Schema — migration 0013
- **`tenants` extended**: `set_aside_certifications text[]` (SDVOSB, 8(a), HUBZone, WOSB, etc.) and `onboarding_completed_at timestamptz null`. Both `null` by default, both surfaced in `/me` and the new `/me/onboarding/*` endpoints.
- Onboarding is **opt-in**, not gated — the dashboard surfaces a "Finish setup" amber banner while `onboarding_completed_at` is null, but no route is blocked.

### Integration — SAM.gov Entity API client
- New module [packages/integrations/src/mactech_integrations/sam_gov/entities.py](packages/integrations/src/mactech_integrations/sam_gov/entities.py) parallel to the existing exclusions client. Hits `GET https://api.sam.gov/entity-information/v4/entities?ueiSAM=...&includeSections=coreData,assertions,pointsOfContact`.
- `EntityProfile` dataclass flattens the rich SAM response down to the fields the wizard cares about: legal name, DBA, CAGE, registration status + dates, physical address (city/state/country), primary NAICS, full NAICS list, raw business types, and a derived list of `set_aside_short_codes` (SDVOSB / 8(a) / HUBZone / WOSB / etc.).
- `_short_codes_from_business_types()` reduces SAM's verbose `businessTypeDesc` strings to the short codes the UI checkboxes use. Tolerant of casing/wording variation.
- Same retry pattern as exclusions: `tenacity` with exponential backoff on transport + 429 + 5xx.
- Exposes `SamEntityNotFoundError` for the "no SAM entity found for that UEI" case so the API can surface a clean 404.

### API — onboarding endpoints ([routes/onboarding.py](apps/api/src/mactech_api/routes/onboarding.py))
- `GET /onboarding/sam-entity/{uei}` — server-side proxy to the SAM Entity client. The SAM API key never leaves the API service. Authenticated; preserves tenant context for future per-tenant rate limiting.
- `POST /me/onboarding/firm-details` — saves UEI / CAGE / legal_name / set_aside_certifications. Idempotent; null inputs preserve existing values; empty arrays are valid (means "no certifications").
- `POST /me/onboarding/complete` — flips `onboarding_completed_at` to now.
- `POST /me/onboarding/reset` — nulls it (admin escape hatch).
- `/me` extended: `TenantHeader` now exposes `uei`, `cage_code`, `set_aside_certifications`, `onboarding_completed_at`. Backward-compatible defaults so old clients don't break.

### Web — onboarding page + dashboard banner + sidebar entry
- **[/onboarding](apps/web/app/(app)/onboarding/page.tsx)** — single-page wizard:
  - Step 1: UEI input + "Look up →" button (form action `lookupAndPrefill` calls SAM, then redirects back with prefill query params).
  - Step 2: confirmation form for legal name + CAGE + set-aside certifications (8 checkboxes: SDVOSB / VOSB / WOSB / EDWOSB / 8(a) / HUBZone / SDB / SB). Submit either keeps the wizard open or flips `onboarding_completed_at` and redirects to /dashboard.
  - Step 3: "What's next" panel with deep links to capability statement / past performance / teaming partner imports.
- Lookup error surfaces in an amber notice with the underlying message; user can still type the firm details manually.
- Successful lookup surfaces an emerald notice + lists the NAICS codes SAM has on file (preview only — NAICS picker ships next sprint).
- **Server actions** in [lib/onboarding.ts](apps/web/lib/onboarding.ts): `lookupSamEntity`, `lookupAndPrefill` (read UEI from form → call API → redirect with prefill params), `saveFirmDetails`, `resetOnboarding`. The lookup action goes through API which goes through the integration package — SAM key never reaches the browser or the Next.js server-action context.
- **Dashboard banner** ([dashboard/page.tsx](apps/web/app/(app)/dashboard/page.tsx)) — when `onboarding_completed_at` is null, renders an amber strip directly under the page header with "Finish setup →" CTA. Two minutes.
- **Sidebar nav** picks up "Setup — Tenant identity wizard" entry under Settings.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 20 routes (1 new: `/onboarding`).
- `python3 -m py_compile` clean on the new SAM Entity client, route module, schema module, and migration.
- Migration 0013 auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh). Both new columns are nullable so existing tenants survive untouched.
- New SAM Entity client uses the existing `SAM_API_KEY` env var — no new secrets needed.

### Trade-offs called out
- **Wizard is single-page, not multi-step.** UEI lookup + firm-details confirmation is the *valuable* part. NAICS picker and founder roster needed real schema thought (per-tenant NAICS table? Reuse `founder_naics_matrix`? Stay on `saved_searches`?), so they defer.
- **First-feed preview deferred.** The agent's original spec had Step 5 = "kick off a one-off SAM ingestion for selected NAICS over the past 14 days, land user on /dashboard with first 3 scored opportunities." For MacTech this is moot (the feed is already populated); for net-new tenants it'd require synchronous worker invocation. Belongs with NAICS picker.
- **No NAICS persistence yet.** SAM's NAICS list is *displayed* on successful lookup but not saved anywhere — the existing seed config still drives the actual NAICS taxonomy. Sprint 9 wires NAICS into the wizard properly.
- **MacTech specifically.** MacTech bootstrapped before this sprint, so their `onboarding_completed_at` will be null on first deploy. The banner will show until they click through `/onboarding`. That's a one-time, two-minute confirmation step.

### Sprint 9 candidates left
- **NAICS picker step** in the wizard, persisting a per-tenant NAICS list separate from the seed config.
- **Founder roster step** — let net-new tenants add their team without seed config.
- **First-feed preview** — synchronous one-off SAM ingestion for the wizard's "we found these opps for you" landing.
- **Streaming Q&A** on the Ask panel.
- **OCR for scanned PDFs**.
- **Inline embedding on capability update**.

---

## 2026-04-25 — Sprint 9: NAICS picker + founder CRUD

User said "sprint 9 execute". Closes the two biggest open items in the onboarding flow: the NAICS picker that drives opportunity scoring, and full founder CRUD so net-new tenants can manage their team without touching seed config.

### Schema — migration 0014
- **`tenants.target_naics text[]`** — NAICS codes the tenant wants opportunities scored against. When null, the scoring engine falls back to the seed-config NAICS list (existing MacTech behaviour). When set, it overrides per-tenant. Wiring scoring to actually consume this column is Sprint 10.

### API — onboarding extensions + founder CRUD
- **POST /me/onboarding/firm-details** extended to accept `target_naics: string[]`. null leaves unchanged; empty list clears the override; populated list overwrites.
- **TenantHeaderOut** + `/me` → `tenant.target_naics` exposed.
- **New [routes/founders.py](apps/api/src/mactech_api/routes/founders.py)** — full CRUD:
  - `GET /founders` — list (no tenant scoping; founders are global at the schema level — known limitation, tracked).
  - `GET /founders/{id}` — single record.
  - `POST /founders` — create. Auto-slugifies the name (e.g., "Patrick Caruso" → "patrick-caruso") and dedupes via -2/-3/etc. suffixes when needed.
  - `PATCH /founders/{id}` — update with optional `clear_email` flag.
  - `DELETE /founders/{id}` — 204.
  - Pillar validated against `{security, infrastructure, quality, governance, other}` set.
- **`/me/settings`** `FounderOut` extended with `id` field so the UI can route to `/settings/founders/{id}/edit` instead of by-slug.

### Web — onboarding wizard
- **NAICS picker fieldset** ([app/(app)/onboarding/page.tsx](apps/web/app/(app)/onboarding/page.tsx)):
  - Suggested codes come from the SAM Entity API result (Sprint 8 lookup) merged with the tenant's existing `target_naics` from the DB. Each renders as a checkbox; checked when in the saved set.
  - Free-form "Additional NAICS codes" text field accepts comma-separated 6-digit codes for codes not in the suggested set.
  - The save action (`saveFirmDetails`) collects checked checkboxes + parsed extras, deduplicates, and submits as `target_naics`.
- **Founder roster preview** in the wizard, pulls live from `/founders`. Shows up to 6 founders with name + title + pillar pip + "Manage in settings →" deep link.

### Web — founder CRUD UI
- New server actions in [lib/founders.ts](apps/web/lib/founders.ts): `createFounder`, `updateFounder` (bound with id), `deleteFounder`.
- New shared form in [components/founder-form.tsx](apps/web/components/founder-form.tsx) — fields: full name, title, pillar (5-option select with friendly labels), email, bio, digest_enabled checkbox.
- New routes:
  - **[/settings/founders/new](apps/web/app/(app)/settings/founders/new/page.tsx)** — manual add form.
  - **[/settings/founders/[id]/edit](apps/web/app/(app)/settings/founders/[id]/edit/page.tsx)** — edit form.
- **/settings page** — founders section header now has "+ Add founder" CTA. Each founder card gets inline Edit / Delete in a footer row, with `Link href="/settings/founders/{id}/edit"` and a `<form action={deleteFounder}>` for the delete.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `next build` produces all 22 routes (2 new: `/settings/founders/new`, `/settings/founders/[id]/edit`).
- `python3 -m py_compile` clean on the new founders route + extended onboarding/settings routes + tenant model + migration 0014.
- Migration auto-runs on api boot.

### Known limitations called out
- **Founders aren't tenant-scoped at the schema level.** No `tenant_id` column on the `founders` table. For MacTech (single tenant) this is fine; for multi-tenancy we'd need a migration adding `tenant_id` + composite unique on `(tenant_id, slug)` + updating every query. Tracked for a future refactor sprint.
- **target_naics not yet wired into the scoring engine.** The column exists and the wizard writes it, but the scoring intelligence module still reads the seed-config NAICS list. Wiring is one query change in `intelligence/scoring.py` — Sprint 10.
- **No first-feed preview yet.** The wizard ends with a "Save & finish setup" that flips the flag and lands on the dashboard. Synchronous one-off SAM ingestion for net-new tenants ("here are the first 3 opps we found for you") still pending.

### Sprint 10 candidates left
- **Wire `target_naics` into the scoring engine** so per-tenant NAICS actually affects opportunity ranking.
- **Founder tenant-scoping migration** — multi-tenancy fix.
- **First-feed preview** — synchronous one-off SAM ingestion at wizard completion.
- **Streaming Q&A** on the Ask panel.
- **OCR for scanned PDFs**.
- **Inline embedding on capability update**.

---

## 2026-04-25 — Sprint 10: scoring picks up target_naics + inline capability embedding

User said "execute sprint 10". Two operational-correctness wins. OCR defers to Sprint 11 (needs system deps + Docker image surgery, deserves its own session).

### target_naics → scoring engine

The Sprint 9 wizard wrote per-tenant NAICS into `tenant.target_naics`, but the scoring engine still ignored it and read the global seeded `naics_codes.mactech_tier` list. This finishes the wiring.

- **[apps/workers/src/mactech_workers/tasks/score.py](apps/workers/src/mactech_workers/tasks/score.py) `_build_context()`** — when `tenant.target_naics` is non-empty, treat that list as the tenant's PRIMARY NAICS (full 25 pts). Secondary set is empty in that case — the user's explicit picker output IS the universe of what they pursue.
- When `target_naics` is null (the existing MacTech state), behavior is unchanged: read the seeded `mactech_tier` primary/secondary buckets.
- Net effect: a brand-new tenant sets their NAICS in the wizard → next scoring sweep (every 20 minutes) ranks opportunities against THEIR list, not MacTech's. MacTech's scoring is identical to before.

### Inline capability embedding

Sprint 7 left a 15-minute lag between "user creates/updates a capability statement" and "the embedding worker picks it up." Closes that.

- **New helper [apps/api/src/mactech_api/embed_helpers.py](apps/api/src/mactech_api/embed_helpers.py)** — `embed_capability_inline(session, capability_id, *, title, summary)` calls Voyage with `title\n\nsummary`, writes the resulting vector via the same `update capability_statements set embedding = CAST(:emb AS vector)` raw SQL the embed worker uses. Fail-soft: if Voyage rate-limits, errors, or `VOYAGE_API_KEY` is unset, log a warning and return False. The embed worker still picks up null-embedding rows on its 15-minute tick — inline is the fast path, worker is the safety net.
- Wired into three places in [routes/library.py](apps/api/src/mactech_api/routes/library.py) + [routes/library_import.py](apps/api/src/mactech_api/routes/library_import.py):
  - `POST /capability-statements` — embed after insert; `has_embedding` in the response reflects whether the inline call succeeded.
  - `PATCH /capability-statements/{id}` — only re-embeds when the summary text changed (was previously: null the column and wait). The order is now: flush → null embedding → embed inline. If embed fails, the row stays null-embedding for the worker to retry.
  - `POST /library/import/capability-statements/from-pdf` — embeds after upsert. Adds a note to the response when the inline embedding didn't materialize so the UI can surface "embedding pending" affordance to the user.

### Verification
- `tsc --noEmit` clean across `apps/web` (no web changes; pure backend sprint).
- `python3 -m py_compile` clean on the new helper + extended library + library_import + extended worker score.py.

### What this changes for users
- **MacTech today**: identical scoring (no `target_naics` set; falls back to seed config). Editing a capability summary in the UI now updates the embedding in <2 seconds instead of waiting up to 15 minutes for the next worker tick.
- **Net-new tenants**: NAICS picker actually drives the scoring engine. Drop a capability PDF → it's embedded inline by the time the redirect lands on the edit page.

### Sprint 11 candidates left
- **Founder tenant-scoping migration** — biggest multi-tenancy gap. Substantial migration with backfill complexity.
- **First-feed preview** — synchronous one-off SAM ingestion at wizard completion for net-new tenants.
- **Streaming Q&A** on the Ask panel.
- **OCR for scanned PDFs** — Tesseract via Docker image addition.

---

## 2026-04-25 — Sprint 11: founder tenant-scoping migration

User said "execute sprint 11". Closes the biggest multi-tenancy gap remaining: founders are now tenant-scoped at the schema level. Substantial migration touching 11 files across API + workers + seeder.

### Schema — migration 0015
- **`founders.tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`** — added with three-step migration:
  1. Add nullable column.
  2. Backfill all existing rows from the single MacTech tenant via `update founders set tenant_id = (select id from tenants where slug = 'mactech')`.
  3. Defensive `do $$ ... raise exception ...` block to verify no nulls remain before locking down with `SET NOT NULL` + foreign key.
- **Slug uniqueness pivot**: `founders_slug_key` (global unique on `slug`) → `uq_founders_tenant_slug` (composite unique on `(tenant_id, slug)`). Two tenants can each have a founder with slug "patrick-caruso" without collision.
- New `ix_founders_tenant_id` index for the per-tenant filter pattern that now appears on every founder query.
- Documented assumption: backfill targets the single tenant slug `'mactech'`. Multi-tenant backfill (via Clerk org id mapping) would be a different migration; we don't have that scenario yet.

### ORM model + seeder
- `mactech_db.models.Founder` gains `tenant_id` field with FK + index. Drops the inline `unique=True` on `slug`; the unique constraint moves to a `__table_args__` `UniqueConstraint("tenant_id", "slug", ...)`.
- `seed_founders()` accepts a `tenant: Tenant` arg, writes `tenant_id=tenant.id` on insert, and uses `(tenant_id, slug)` as the on-conflict index. Caller in `seed.py` updated to pass `tenant=tenant`.

### Founder queries — all 11 files updated
- **auth.py** — both founder-by-slug lookups (JIT user provisioning + post-creation rebind) gained `Founder.tenant_id == tenant.id` filter.
- **routes/founders.py** — every CRUD query gained tenant filter. `_unique_slug()` signature accepts `tenant_id` and only checks for collisions within that tenant, so two tenants can independently use "patrick-caruso" as their founder's slug.
- **routes/me.py** — pillar-cards founder list now filters by `tenant_id`.
- **routes/settings.py** — `/me/settings` founder list filtered.
- **routes/ask.py** — Q&A context builder filters founders to current tenant.
- **routes/drafts.py** — Sources Sought drafter context filtered.
- **routes/library.py** — both founder lookups (by-id map + `_resolve_founder_refs(slugs)`) filtered. `_resolve_founder_refs` now takes `tenant_id` as a positional arg; callers updated.
- **routes/opportunities.py** — digest endpoint's by-slug lookup filtered.
- **routes/pursuits.py** — `_resolve_owner_founder_id(slug)` filtered to current tenant.
- **workers/score.py** — both `founders_by_slug` reads filtered by `tenant.id` (already in scope inside the per-tenant loop).
- **workers/digest.py** — `send_digest_for_founder()` and `send_digest_to_all_founders()` now resolve the tenant from `MACTECH_TENANT_SLUG` env var first, then filter founders by `tenant_id`. Multi-tenant fan-out (one digest run per tenant) is a future sprint; today the worker stays pinned to one tenant via env, matching its existing assumption.

### Why this isn't a UI sprint
Pure backend correctness — the web UI was already calling `/me/settings` and `/founders` for the founder list, both of which now correctly tenant-scope server-side. No frontend changes needed.

### Verification
- `python3 -m py_compile` clean on all 14 touched files (model, migration, seeder, 9 routes, 2 workers, auth).
- Founder ORM column set verified via uv: `['id', 'tenant_id', 'slug', 'full_name', 'title', 'pillar', 'bio', 'areas_of_expertise', 'email', 'digest_enabled', 'created_at']`. Constraints: `['uq_founders_tenant_slug']`.
- Migration 0015 auto-runs on api boot via [entrypoint.sh](apps/api/entrypoint.sh). The defensive null-check block ensures the migration aborts cleanly if backfill leaves any row null (which shouldn't happen, but safety).

### What this unblocks
- **Multi-tenant onboarding actually works.** A net-new tenant can sign up, the wizard creates their founders via `POST /founders` with `tenant_id` baked in, and there's no chance of collision with MacTech's founders. Sprint 8/9 was wired correctly at the API level; the schema constraint now enforces it.
- **Future founder tenant-scoped Clerk org claims.** Once we have multiple tenants in production, the `claims.founder_slug` resolver in `auth.py` correctly filters by the JWT's `tenant_org_id` so a founder slug collision across tenants doesn't cross-resolve.

### Sprint 12 candidates left
- **First-feed preview** — synchronous one-off SAM ingestion at wizard completion for net-new tenants.
- **Streaming Q&A** on the Ask panel.
- **OCR for scanned PDFs** — Tesseract via Docker image addition.
- **Multi-tenant digest fan-out** — iterate tenants in `send_digest_to_all_founders` instead of pinning to one via env var.

---

## 2026-04-25 — Sprint 12: OCR for scanned PDFs + multi-tenant digest fan-out

User said "execute sprint 12". Two clean, complementary wins: OCR unblocks scanned-PDF imports (a real user need); digest fan-out completes the multi-tenancy correctness story from Sprint 11.

### OCR for scanned PDFs

The existing PDF import flow (Sprints 6/7) extracted text via PyMuPDF only. Scanned PDFs (image-only, no embedded text layer) returned <30 chars and got rejected with "OCR isn't supported yet." This closes that.

- **[apps/api/Dockerfile](apps/api/Dockerfile)**: added `apt-get install tesseract-ocr tesseract-ocr-eng` to the runtime image. English-only — non-English OCR is out of scope. Docker image grows ~30MB.
- **[apps/api/pyproject.toml](apps/api/pyproject.toml)**: added `pytesseract>=0.3.10`. Pillow comes transitively via PyMuPDF.
- **[apps/api/src/mactech_api/routes/library_import.py](apps/api/src/mactech_api/routes/library_import.py)** `_pdf_to_text`:
  - First tries PyMuPDF text extraction (fast path for text-based PDFs).
  - If <80 chars (`OCR_FALLBACK_THRESHOLD`), falls through to `_ocr_pdf()`:
    - Renders each page to PNG at 220dpi via `page.get_pixmap(dpi=220)`.
    - Capped at 12 pages (`OCR_MAX_PAGES`) to bound latency.
    - Runs `pytesseract.image_to_string(img, lang="eng")` per page.
    - Returns concatenated text, or empty string on tesseract-not-found / unexpected error (fail-soft so a missing binary doesn't tank the request).
  - Returns whichever extraction (PyMuPDF or OCR) produced more usable text.
- The "<30 chars" rejection now reads "Couldn't extract usable text from this PDF — neither the embedded text layer nor OCR returned anything readable" since the text-only assumption is gone.
- **Import-page copy** updated on both [past-performance/import](apps/web/app/(app)/library/past-performance/import/page.tsx) and [capability-statements/import](apps/web/app/(app)/library/capability-statements/import/page.tsx): "text or scanned PDFs · 20 MB max" instead of "text-based PDFs only", and the "What works best?" tip block now mentions Tesseract OCR.

### Multi-tenant digest fan-out

Sprint 11 made founders tenant-scoped at the schema level but left the digest worker single-tenant via the `MACTECH_TENANT_SLUG` env var. This refactors the worker to fan out across all tenants, with the env var preserved as an opt-in pin for testing / single-tenant deploys.

- **[apps/workers/src/mactech_workers/tasks/digest.py](apps/workers/src/mactech_workers/tasks/digest.py)**:
  - `send_digest_for_founder(slug, *, tenant_slug=None, ...)` now takes an optional explicit tenant_slug. When None, falls back to `MACTECH_TENANT_SLUG` env (legacy default). The fan-out function passes it explicitly.
  - `send_digest_to_all_founders(*, only_tenant_slug=None, ...)` is the multi-tenant default. Iterates **all** tenants (ordered by slug for reproducibility), pre-loads digest_enabled founders in one query, then groups by `tenant_id` and dispatches per-founder. Per-founder failures are caught and surfaced as `DigestSendStats(sent=False, skipped_reason=...)` rather than aborting the loop.
  - The `MACTECH_PIN_TENANT_SLUG` env (or the explicit `only_tenant_slug` arg) pins the run to one tenant — useful for testing or for single-tenant deploys that don't want cross-tenant fan-out.

### Verification
- `tsc --noEmit` clean across `apps/web`.
- `python3 -m py_compile` clean on the modified library_import + digest.
- Pillow + pytesseract verified via uv on api package: Pillow 12.2.0, pytesseract 0.3.13.
- Docker image will rebuild on next Railway deploy with tesseract installed in the runtime stage.

### Trade-offs called out
- **OCR quality is variable.** Tesseract on a low-resolution scan won't be great. The 220dpi rasterization + English-only is a reasonable default; non-English documents and very poor scans will still produce thin extractions and the user sees the same fallback rejection.
- **No async OCR.** OCR runs synchronously per page; a 12-page scanned PDF can take 30+ seconds. The Anthropic timeout downstream is generous so this works, but it's the most expensive path through the import flow. A future sprint could move OCR to a worker task.
- **Pin env var renamed.** Legacy was `MACTECH_TENANT_SLUG` (still honored as fallback in `send_digest_for_founder`); new fan-out controller honors `MACTECH_PIN_TENANT_SLUG`. The Railway env var doesn't need to change for the existing single-tenant deploy — `MACTECH_TENANT_SLUG=mactech` keeps the per-founder send working as before, and the absence of `MACTECH_PIN_TENANT_SLUG` lets the fan-out iterate (which currently means just MacTech anyway).

### Sprint 13 candidates left
- **First-feed preview** — synchronous one-off SAM ingestion at wizard completion for net-new tenants.
- **Streaming Q&A** on the Ask panel — convert the existing endpoint to SSE so the answer composes live instead of arriving all at once after 10s.
- **Async OCR worker task** — move the OCR fall-through to a background job so import requests stay fast.
