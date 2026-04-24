#!/usr/bin/env bash
# Entrypoint for the mactech-api Railway service.
# 1. Apply Alembic migrations (idempotent, safe to run on every boot)
# 2. Launch uvicorn bound to Railway's $PORT.
#
# Seed is NOT run here — first-run seeding is a one-off via `railway run`
# to keep the boot path fast and avoid write amplification on every restart.

set -euo pipefail

echo "[entrypoint] applying database migrations..."
(cd /app/packages/db && alembic upgrade head)

PORT="${PORT:-8000}"
echo "[entrypoint] starting uvicorn on 0.0.0.0:${PORT}"
exec uvicorn mactech_api.main:app --host 0.0.0.0 --port "${PORT}"
