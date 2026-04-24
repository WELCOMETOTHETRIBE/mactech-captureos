#!/usr/bin/env bash
# Entrypoint for the mactech-workers Railway service.
# Runs celery worker + beat in a single process. Migrations are NOT
# applied here — apps/api owns that path. The api will be running by the
# time this container starts (or it will, on first ever deploy; eventual
# consistency is fine because we have no schema-dependent task in startup).

set -euo pipefail

echo "[entrypoint] starting celery worker + beat (america/new_york tz)"
exec celery -A mactech_workers.celery_app worker --beat --loglevel=info \
    --concurrency=2 \
    --max-tasks-per-child=200
