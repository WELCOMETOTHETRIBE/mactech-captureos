"""DATABASE_URL scheme normalization.

Railway, Heroku, and most managed Postgres providers inject `postgresql://...`
(or legacy `postgres://...`). SQLAlchemy's async engine needs the driver name
embedded in the scheme: `postgresql+asyncpg://...`. Normalize at every read
site so the same env var works in dev and prod without manual rewriting.
"""

from __future__ import annotations


def to_asyncpg_url(value: str) -> str:
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+asyncpg://" + value[len("postgresql://") :]
    return value
