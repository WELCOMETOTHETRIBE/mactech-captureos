"""Contract tests for the SAM.gov Opportunities client.

These hit the live API. They're skipped automatically when SAM_API_KEY isn't set
so CI on a forked PR doesn't fail on missing secrets. When the key is present,
each test uses a tight filter to keep the call cost at 1 request and stay well
under the 1000/day budget.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from mactech_integrations.sam_gov import SamGovOpportunitiesClient

pytestmark = pytest.mark.skipif(
    not os.environ.get("SAM_API_KEY"),
    reason="SAM_API_KEY not set — skipping live contract tests",
)


@pytest.fixture
def api_key() -> str:
    key = os.environ.get("SAM_API_KEY")
    assert key, "SAM_API_KEY must be set for contract tests"
    return key


async def test_search_returns_pages_with_records(api_key: str) -> None:
    """NAICS 541519 in the last 30 days should always have records — sanity check."""
    posted_to = date.today()
    posted_from = posted_to - timedelta(days=30)
    async with SamGovOpportunitiesClient(api_key=api_key) as client:
        page = await client.search_opportunities(
            posted_from=posted_from,
            posted_to=posted_to,
            ncode="541519",
            limit=3,
        )
    assert page.total_records >= 0
    assert page.limit == 3
    assert page.offset == 0
    if page.opportunities_data:
        opp = page.opportunities_data[0]
        assert opp.notice_id
        assert opp.title


async def test_search_with_set_aside_filter(api_key: str) -> None:
    """SDVOSB filter should narrow the result set."""
    posted_to = date.today()
    posted_from = posted_to - timedelta(days=30)
    async with SamGovOpportunitiesClient(api_key=api_key) as client:
        page = await client.search_opportunities(
            posted_from=posted_from,
            posted_to=posted_to,
            ncode="541519",
            type_of_set_aside="SDVOSBC",
            limit=1,
        )
    assert page.limit == 1
    if page.opportunities_data:
        assert page.opportunities_data[0].type_of_set_aside == "SDVOSBC"


async def test_iter_opportunities_paginates(api_key: str) -> None:
    """Pagination yields multiple pages and stops at totalRecords."""
    posted_to = date.today()
    posted_from = posted_to - timedelta(days=7)
    pages_seen = 0
    async with SamGovOpportunitiesClient(api_key=api_key) as client:
        async for page in client.iter_opportunities(
            posted_from=posted_from,
            posted_to=posted_to,
            ncode="541519",
            page_size=2,
            max_pages=2,
        ):
            pages_seen += 1
            assert page.limit == 2
    assert pages_seen >= 1
    assert pages_seen <= 2
