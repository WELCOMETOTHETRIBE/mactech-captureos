# MacTech CaptureOS

**The operating system for defense contractors.**

Identify, win, and stay eligible for federal work — capture intelligence, proposal automation, and CMMC readiness in one platform built by the team that uses it to win contracts themselves.

---

## Quick start

```bash
# First-time setup
cp .env.example .env          # fill in API keys (see docs/DATA_SOURCES.md)
docker compose up -d          # starts Postgres + Redis + MinIO
cd apps/api && uv sync        # Python deps
cd apps/web && pnpm install   # Node deps
pnpm db:migrate               # run migrations
pnpm dev                      # starts api + web + workers concurrently
```

Web: http://localhost:3000
API: http://localhost:8000/docs
MinIO console: http://localhost:9001

## Repo map

- `apps/api` — FastAPI backend
- `apps/web` — Next.js 14 frontend
- `apps/workers` — Celery ingestion workers
- `packages/db` — Shared SQLAlchemy models & Alembic migrations
- `packages/integrations` — External API clients (SAM.gov, USASpending, Apify, SerpAPI, Anthropic)
- `packages/intelligence` — Scoring, parsing, compliance matrix logic
- `docs/` — Product spec, architecture, data sources, roadmap, positioning
- `data/` — Seed data: founders, NAICS matrix

## For Claude Code

If you're an AI coding agent working on this repo: start with `CLAUDE.md`.

## Ownership

MacTech Solutions LLC • SDVOSB-certified • Veteran-Owned
https://www.mactechsolutionsllc.com

Copyright © 2026 MacTech Solutions LLC. All rights reserved.
