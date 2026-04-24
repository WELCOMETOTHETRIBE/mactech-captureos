import os
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from mactech_db.url import to_asyncpg_url


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_async_engine(to_asyncpg_url(url), pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, class_=AsyncSession)
