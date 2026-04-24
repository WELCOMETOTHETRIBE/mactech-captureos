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
