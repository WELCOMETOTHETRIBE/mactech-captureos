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
