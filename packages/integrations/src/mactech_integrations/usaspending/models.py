"""Pydantic models for USASpending.gov API responses.

We model only the fields MacTech consumes; everything else stays in the
raw_payload column. Loose config (extra=ignore) keeps us forward-compatible
when USASpending adds fields. Do NOT add `from __future__ import annotations`
here — pydantic v2 needs runtime-resolvable annotations.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class PageMetadata(_Loose):
    page: int = 1
    has_next: bool = Field(default=False, alias="hasNext")
    has_previous: bool = Field(default=False, alias="hasPrevious")
    last_record_unique_id: int | None = None
    last_record_sort_value: str | None = None
    next: int | None = None
    previous: int | None = None
    count: int | None = None


class AwardSearchResult(_Loose):
    """One row from POST /api/v2/search/spending_by_award/."""

    internal_id: int | None = None
    generated_internal_id: str | None = None
    award_id_field: str | None = Field(default=None, alias="Award ID")
    recipient_name: str | None = Field(default=None, alias="Recipient Name")
    recipient_uei: str | None = Field(default=None, alias="Recipient UEI")
    award_amount: Decimal | None = Field(default=None, alias="Award Amount")
    description: str | None = Field(default=None, alias="Description")
    awarding_agency: str | None = Field(default=None, alias="Awarding Agency")
    awarding_subagency: str | None = Field(default=None, alias="Awarding Sub Agency")
    contract_award_type: str | None = Field(default=None, alias="Contract Award Type")
    period_of_performance_start_date: date | None = Field(
        default=None, alias="Period of Performance Start Date"
    )
    period_of_performance_current_end_date: date | None = Field(
        default=None, alias="Period of Performance Current End Date"
    )
    # USASpending returns these as objects {"code": str, "description": str},
    # not bare strings. We don't use them in enrichment (we already have the
    # opp's naics_code), so keep them as a flexible dict.
    naics_field: dict[str, Any] | None = Field(default=None, alias="NAICS")
    psc_field: dict[str, Any] | None = Field(default=None, alias="PSC")
    raw: dict[str, Any] | None = None  # populated by client.search_awards via model_dump


class AwardSearchPage(_Loose):
    spending_level: str | None = None
    limit: int | None = None
    results: list[AwardSearchResult] = Field(default_factory=list)
    page_metadata: PageMetadata | None = None
    messages: list[str] | None = None


class RecipientSearchHit(_Loose):
    """One result from POST /api/v2/recipient/."""

    id: str  # the <uuid>-<C|P|R> hash
    name: str | None = None
    uei: str | None = None
    duns: str | None = None
    amount: Decimal | None = None
    recipient_level: str | None = None


class RecipientSearchPage(_Loose):
    page_metadata: PageMetadata | None = None
    results: list[RecipientSearchHit] = Field(default_factory=list)


class RecipientTotals(_Loose):
    contract_amount: Decimal | None = None
    assistance_amount: Decimal | None = None
    transactions: int | None = None


class RecipientProfile(_Loose):
    """GET /api/v2/recipient/duns/<HASH>/."""

    name: str | None = None
    uei: str | None = None
    duns: str | None = None
    parent_name: str | None = None
    parent_uei: str | None = None
    recipient_level: str | None = None
    business_types: list[str] | None = None
    total_amounts: RecipientTotals | None = None
    location: dict[str, Any] | None = None
