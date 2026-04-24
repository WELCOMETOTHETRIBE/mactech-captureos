from fastapi import FastAPI
from sqlalchemy import text

from mactech_api.settings import settings
from mactech_db import async_session_factory

app = FastAPI(
    title="MacTech CaptureOS API",
    version="0.1.0",
    description="The operating system for defense contractors.",
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    session_factory = async_session_factory()
    async with session_factory() as session:
        await session.execute(text("select 1"))
    return {"status": "ready"}
