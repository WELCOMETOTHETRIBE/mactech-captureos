# syntax=docker/dockerfile:1.7
# mactech-workers Railway service.
# Same builder pattern as apps/api/Dockerfile — repo-root build context,
# uv-based multi-stage. Runtime entrypoint runs celery worker + beat in
# a single process. Workers do not bind a port; no /healthz endpoint.
FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY pyproject.toml ./
COPY apps/api/pyproject.toml apps/api/
COPY apps/workers/pyproject.toml apps/workers/
COPY packages/db/pyproject.toml packages/db/
COPY packages/integrations/pyproject.toml packages/integrations/
COPY packages/intelligence/pyproject.toml packages/intelligence/

COPY packages/db/src packages/db/src
COPY packages/integrations/src packages/integrations/src
COPY packages/intelligence/src packages/intelligence/src
COPY apps/workers/src apps/workers/src
COPY apps/api/src apps/api/src
COPY apps/api/scripts apps/api/scripts

RUN uv sync --all-packages --no-dev

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder /app /app

# Workers consume the same data + config as api for ad-hoc admin paths.
COPY config config
COPY data data
COPY packages/db/alembic packages/db/alembic
COPY packages/db/alembic.ini packages/db/alembic.ini

COPY apps/workers/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

CMD ["/usr/local/bin/entrypoint.sh"]
