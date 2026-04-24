"""Idempotent MacTech tenant seeder.

Loads:
  - config/mactech_tenant_defaults.yml  → tenant + saved searches + scoring config
  - data/founders.json                  → 4 founders
  - data/naics_matrix.json              → 20 NAICS codes + founder-NAICS affinity

Run:
  cd apps/api && uv run python -m scripts.seed

Safe to re-run — every write is an upsert.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from mactech_db import async_session_factory
from mactech_db.models import (
    CapabilityStatement,
    Founder,
    FounderNaicsMatrix,
    NaicsCode,
    SavedSearch,
    Tenant,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "mactech_tenant_defaults.yml"
FOUNDERS_PATH = REPO_ROOT / "data" / "founders.json"
NAICS_PATH = REPO_ROOT / "data" / "naics_matrix.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


async def seed_tenant(session: AsyncSession, config: dict[str, Any]) -> Tenant:
    t = config["tenant"]
    stmt = (
        pg_insert(Tenant)
        .values(
            slug=t["slug"],
            name=t["name"],
            plan=t.get("plan", "internal"),
            uei=t.get("uei"),
            cage_code=t.get("cage_code"),
        )
        .on_conflict_do_update(
            index_elements=["slug"],
            set_={
                "name": t["name"],
                "plan": t.get("plan", "internal"),
                "uei": t.get("uei"),
                "cage_code": t.get("cage_code"),
            },
        )
    )
    await session.execute(stmt)
    tenant = (await session.execute(select(Tenant).where(Tenant.slug == t["slug"]))).scalar_one()
    return tenant


async def seed_naics(session: AsyncSession, naics_doc: dict[str, Any]) -> None:
    for entry in naics_doc["naics_codes"]:
        stmt = (
            pg_insert(NaicsCode)
            .values(
                code=entry["code"],
                title=entry["title"],
                description=entry.get("why_fits"),
                mactech_tier=entry["tier"],
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "title": entry["title"],
                    "description": entry.get("why_fits"),
                    "mactech_tier": entry["tier"],
                },
            )
        )
        await session.execute(stmt)


async def seed_founders(
    session: AsyncSession, founders_doc: dict[str, Any], naics_doc: dict[str, Any]
) -> dict[str, Founder]:
    by_slug: dict[str, Founder] = {}
    for f in founders_doc["founders"]:
        stmt = (
            pg_insert(Founder)
            .values(
                slug=f["slug"],
                full_name=f["full_name"],
                title=f["title"],
                pillar=f["pillar"],
                bio=f.get("pillar_description"),
                areas_of_expertise={
                    "expertise": f.get("areas_of_expertise", []),
                    "proposal_role": f.get("proposal_role"),
                    "security_clearance_status": f.get("security_clearance_status"),
                    "bar_licensure": f.get("bar_licensure"),
                    "prior_experience": f.get("prior_experience"),
                },
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "full_name": f["full_name"],
                    "title": f["title"],
                    "pillar": f["pillar"],
                    "bio": f.get("pillar_description"),
                },
            )
        )
        await session.execute(stmt)

    for f in founders_doc["founders"]:
        founder = (
            await session.execute(select(Founder).where(Founder.slug == f["slug"]))
        ).scalar_one()
        by_slug[f["slug"]] = founder

    # founder_naics_matrix from naics_matrix.json (authoritative for affinity).
    for entry in naics_doc["naics_codes"]:
        for slug in entry.get("founders", []):
            founder = by_slug.get(slug)
            if founder is None:
                print(f"  warn: naics {entry['code']} references unknown founder slug {slug!r}")
                continue
            stmt = (
                pg_insert(FounderNaicsMatrix)
                .values(founder_id=founder.id, naics_code=entry["code"], affinity=1)
                .on_conflict_do_nothing(index_elements=["founder_id", "naics_code"])
            )
            await session.execute(stmt)

    return by_slug


async def seed_capability_statements(
    session: AsyncSession,
    tenant: Tenant,
    founders_by_slug: dict[str, Founder],
    config: dict[str, Any],
) -> None:
    """Upsert MacTech's capability statements from config yaml.

    Phase 1: this overwrites admin edits on every run because no UI exists
    to make admin edits in the first place. When a capability-edit UI ships
    in Phase 2, this seed should switch to insert-only or be retired.
    """
    statements = config.get("capability_statements_seed") or []
    for s in statements:
        related_founder_records = []
        for slug in s.get("related_founders", []) or []:
            f = founders_by_slug.get(slug)
            if f is None:
                continue
            related_founder_records.append({"founder_id": str(f.id), "slug": slug})

        existing = (
            await session.execute(
                select(CapabilityStatement).where(
                    CapabilityStatement.tenant_id == tenant.id,
                    CapabilityStatement.title == s["title"],
                )
            )
        ).scalar_one_or_none()

        related_naics = [str(n) for n in (s.get("related_naics") or [])]
        if existing is None:
            session.add(
                CapabilityStatement(
                    tenant_id=tenant.id,
                    title=s["title"],
                    summary=s["summary"].strip(),
                    related_naics=related_naics,
                    related_founders=related_founder_records,
                )
            )
        else:
            existing.summary = s["summary"].strip()
            existing.related_naics = related_naics
            existing.related_founders = related_founder_records


async def seed_saved_searches(
    session: AsyncSession,
    tenant: Tenant,
    founders_by_slug: dict[str, Founder],
    config: dict[str, Any],
) -> None:
    for s in config.get("saved_searches", []):
        owner = founders_by_slug.get(s["owner_slug"])
        if owner is None:
            print(f"  warn: saved_search {s['name']!r} references unknown founder {s['owner_slug']!r}")
            continue

        existing = (
            await session.execute(
                select(SavedSearch).where(
                    SavedSearch.tenant_id == tenant.id, SavedSearch.name == s["name"]
                )
            )
        ).scalar_one_or_none()

        filters = s.get("filters", {})
        alert_threshold = s.get("alert_threshold", 70)
        alert_cadence = s.get("alert_cadence", "daily")
        alert_channels = s.get("alert_channels", ["email"])

        if existing is None:
            session.add(
                SavedSearch(
                    tenant_id=tenant.id,
                    owner_founder_id=owner.id,
                    name=s["name"],
                    filters=filters,
                    alert_threshold=alert_threshold,
                    alert_cadence=alert_cadence,
                    alert_channels=alert_channels,
                )
            )
        else:
            existing.owner_founder_id = owner.id
            existing.filters = filters
            existing.alert_threshold = alert_threshold
            existing.alert_cadence = alert_cadence
            existing.alert_channels = alert_channels


async def main() -> int:
    for path in (CONFIG_PATH, FOUNDERS_PATH, NAICS_PATH):
        if not path.exists():
            print(f"ERROR: required file missing: {path}", file=sys.stderr)
            return 1

    config = _load_yaml(CONFIG_PATH)
    founders_doc = _load_json(FOUNDERS_PATH)
    naics_doc = _load_json(NAICS_PATH)

    session_factory = async_session_factory()
    async with session_factory() as session:
        async with session.begin():
            print(f"seeding tenant {config['tenant']['slug']!r}...")
            tenant = await seed_tenant(session, config)

            print(f"seeding {len(naics_doc['naics_codes'])} NAICS codes...")
            await seed_naics(session, naics_doc)

            print(f"seeding {len(founders_doc['founders'])} founders + NAICS matrix...")
            founders_by_slug = await seed_founders(session, founders_doc, naics_doc)

            print(
                f"seeding {len(config.get('capability_statements_seed', []))} capability statements..."
            )
            await seed_capability_statements(session, tenant, founders_by_slug, config)

            print(f"seeding {len(config.get('saved_searches', []))} saved searches...")
            await seed_saved_searches(session, tenant, founders_by_slug, config)

    print("seed complete.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
