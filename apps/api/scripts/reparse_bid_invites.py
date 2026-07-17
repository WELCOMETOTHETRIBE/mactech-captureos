"""One-off: re-run the BuildingConnected parser over every bid_invites row.

Companion to POST /bid-invites/reparse for when there's no Clerk
session handy (ops shell). Reads DATABASE_URL from the environment —
run it with the service env injected, never with a pasted URL:

    railway run --service mactech-api -- python apps/api/scripts/reparse_bid_invites.py

Falls back to DATABASE_PUBLIC_URL when DATABASE_URL points at
Railway's internal hostname (unreachable from a laptop).
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

from mactech_db.models import BidInvite
from mactech_intelligence.bid_invite_parser import parse_bid_invite
from mactech_intelligence.bid_invite_routing import project_group_key
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if ".railway.internal" in url and os.environ.get("DATABASE_PUBLIC_URL"):
        url = os.environ["DATABASE_PUBLIC_URL"]
    if not url:
        sys.exit("DATABASE_URL not set — run via `railway run`.")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


async def main() -> None:
    engine = create_async_engine(_database_url())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    async with factory() as session, session.begin():
        rows = (await session.execute(select(BidInvite))).scalars().all()
        for inv in rows:
            parsed = parse_bid_invite(inv.subject, inv.text_body)
            inv.kind = parsed.kind
            inv.project_name = parsed.project_name
            inv.bid_package = parsed.bid_package
            inv.gc_company = parsed.gc_company
            inv.lead_name = parsed.lead_name
            inv.lead_email = parsed.lead_email
            inv.lead_phone = parsed.lead_phone
            inv.location = parsed.location
            inv.bid_due_on = parsed.bid_due_on
            inv.rfp_id = parsed.rfp_id
            inv.rfp_url = parsed.rfp_url
            inv.headline = parsed.headline
            inv.group_key = project_group_key(parsed.project_name, inv.subject)
            inv.parsed_at = now
    await engine.dispose()
    print(f"reparsed {len(rows)} bid invites")


if __name__ == "__main__":
    asyncio.run(main())
