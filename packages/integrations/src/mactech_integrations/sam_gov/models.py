"""Pydantic models mirroring the SAM.gov Get Opportunities Public API v2.

The API schema is documented in docs/SAM_GOV_API.md and verified via live calls
on 2026-04-24. We model the fields MacTech actually consumes; everything else
stays in the raw_payload jsonb on the persistence side.

Fields are typed loosely (Optional[str] instead of strict enums) because SAM.gov
quietly evolves the schema and we'd rather log unknown values than crash ingest.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    """Base model that ignores unexpected fields (forward-compat)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class OpportunityAwardeeLocation(_Loose):
    street_address: str | None = Field(default=None, alias="streetAddress")
    city: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    zip: str | None = None
    country: dict[str, Any] | None = None


class OpportunityAwardee(_Loose):
    name: str | None = None
    location: OpportunityAwardeeLocation | None = None
    uei_sam: str | None = Field(default=None, alias="ueiSAM")
    cage_code: str | None = Field(default=None, alias="cageCode")


class OpportunityAward(_Loose):
    date: date | None = None
    number: str | None = None
    amount: str | None = None  # SAM returns this as a string
    awardee: OpportunityAwardee | None = None


class OpportunityPointOfContact(_Loose):
    fax: str | None = None
    type: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    full_name: str | None = Field(default=None, alias="fullName")


class OpportunityOfficeAddress(_Loose):
    zipcode: str | None = None
    city: str | None = None
    country_code: str | None = Field(default=None, alias="countryCode")
    state: str | None = None


class OpportunityPlaceOfPerformance(_Loose):
    city: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    country: dict[str, Any] | None = None
    zip: str | None = None
    street_address: str | None = Field(default=None, alias="streetAddress")


class OpportunityLink(_Loose):
    rel: str | None = None
    href: str | None = None


class OpportunityRecord(_Loose):
    """One opportunity from /opportunities/v2/search."""

    notice_id: str = Field(alias="noticeId")
    title: str
    solicitation_number: str | None = Field(default=None, alias="solicitationNumber")
    full_parent_path_name: str | None = Field(default=None, alias="fullParentPathName")
    full_parent_path_code: str | None = Field(default=None, alias="fullParentPathCode")
    posted_date: date | None = Field(default=None, alias="postedDate")
    type: str | None = None
    base_type: str | None = Field(default=None, alias="baseType")
    archive_type: str | None = Field(default=None, alias="archiveType")
    archive_date: date | None = Field(default=None, alias="archiveDate")
    type_of_set_aside_description: str | None = Field(
        default=None, alias="typeOfSetAsideDescription"
    )
    type_of_set_aside: str | None = Field(default=None, alias="typeOfSetAside")
    response_deadline: datetime | None = Field(default=None, alias="responseDeadLine")
    naics_code: str | None = Field(default=None, alias="naicsCode")
    naics_codes: list[str] | None = Field(default=None, alias="naicsCodes")
    classification_code: str | None = Field(default=None, alias="classificationCode")
    active: str | None = None
    award: OpportunityAward | None = None
    point_of_contact: list[OpportunityPointOfContact] | None = Field(
        default=None, alias="pointOfContact"
    )
    description: str | None = None  # NB: this is a URL, not the text. See docs/SAM_GOV_API.md §4.
    organization_type: str | None = Field(default=None, alias="organizationType")
    office_address: OpportunityOfficeAddress | None = Field(default=None, alias="officeAddress")
    place_of_performance: OpportunityPlaceOfPerformance | None = Field(
        default=None, alias="placeOfPerformance"
    )
    additional_info_link: str | None = Field(default=None, alias="additionalInfoLink")
    ui_link: str | None = Field(default=None, alias="uiLink")
    links: list[OpportunityLink] | None = None
    resource_links: list[str] | None = Field(default=None, alias="resourceLinks")


class OpportunitySearchResponse(_Loose):
    total_records: int = Field(alias="totalRecords")
    limit: int
    offset: int
    opportunities_data: list[OpportunityRecord] = Field(default_factory=list, alias="opportunitiesData")
    links: list[OpportunityLink] | None = None
