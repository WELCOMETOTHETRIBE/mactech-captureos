# syntax=docker/dockerfile:1.7
# Build context is the REPO ROOT (set via railway.json rootDirectory = "."),
# so paths below are repo-root relative.
FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Workspace declarations first — keeps the dependency install cacheable.
COPY pyproject.toml ./
COPY apps/api/pyproject.toml apps/api/
COPY apps/workers/pyproject.toml apps/workers/
COPY packages/db/pyproject.toml packages/db/
COPY packages/integrations/pyproject.toml packages/integrations/
COPY packages/intelligence/pyproject.toml packages/intelligence/

# Source for every workspace package (needed because uv resolves workspace members).
COPY packages/db/src packages/db/src
COPY packages/integrations/src packages/integrations/src
COPY packages/intelligence/src packages/intelligence/src
COPY apps/workers/src apps/workers/src
COPY apps/api/src apps/api/src
COPY apps/api/scripts apps/api/scripts

# Install ALL workspace packages so the api container can also run worker
# tasks ad-hoc via `railway ssh` (manual ingestion smoke tests, one-off
# admin invocations). Slight image-size cost is fine at our scale; a
# proper split-image setup is a phase-2 chore once we add a dedicated
# Railway workers service.
RUN uv sync --all-packages --no-dev

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /app /app

# Seed + migrations run at startup, so ship the inputs they read.
COPY config config
COPY data data
COPY packages/db/alembic packages/db/alembic
COPY packages/db/alembic.ini packages/db/alembic.ini

COPY apps/api/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000
CMD ["/usr/local/bin/entrypoint.sh"]
