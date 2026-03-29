"""
Pydantic v2 response models for all GrantFlow API endpoints.

These models lock the API schema so field names never accidentally change
when internal ORM model fields change (stable contract per API-03).
All ORM-backed models use ConfigDict(from_attributes=True) so that
.model_validate(orm_obj) works directly on SQLAlchemy objects.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Award
# ---------------------------------------------------------------------------


class AwardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    award_id: Optional[str] = None
    title: Optional[str] = None
    recipient_name: Optional[str] = None
    award_amount: Optional[float] = None
    award_date: Optional[str] = None
    agency_name: Optional[str] = None
    place_state: Optional[str] = None
    place_city: Optional[str] = None


# ---------------------------------------------------------------------------
# Opportunity (list / search results)
# ---------------------------------------------------------------------------


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    source_id: str
    title: str
    description: Optional[str] = None
    agency_code: Optional[str] = None
    agency_name: Optional[str] = None
    opportunity_number: Optional[str] = None
    opportunity_status: Optional[str] = None
    funding_instrument: Optional[str] = None
    category: Optional[str] = None
    cfda_numbers: Optional[str] = None
    # Stored as a JSON string in the Text column — not parsed here (out of scope)
    eligible_applicants: Optional[str] = None
    post_date: Optional[str] = None
    close_date: Optional[str] = None
    last_updated: Optional[str] = None
    award_floor: Optional[float] = None
    award_ceiling: Optional[float] = None
    estimated_total_funding: Optional[float] = None
    expected_number_of_awards: Optional[int] = None
    cost_sharing_required: Optional[bool] = None
    contact_email: Optional[str] = None
    contact_text: Optional[str] = None
    additional_info_url: Optional[str] = None
    source_url: Optional[str] = None
    topic_tags: Optional[str] = None
    canonical_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Opportunity detail (single record — includes awards)
# ---------------------------------------------------------------------------


class OpportunityDetailResponse(OpportunityResponse):
    awards: list[AwardResponse] = []


# ---------------------------------------------------------------------------
# Paginated search response
# ---------------------------------------------------------------------------


class SearchResponse(BaseModel):
    results: list[OpportunityResponse]
    total: int
    page: int
    per_page: int
    pages: int


# ---------------------------------------------------------------------------
# Key creation response (used by keys.py / Plan 01)
# ---------------------------------------------------------------------------


class KeyCreateResponse(BaseModel):
    key: str
    key_prefix: str
    tier: str
    created_at: str


# ---------------------------------------------------------------------------
# Agency response (API-08)
# ---------------------------------------------------------------------------


class AgencyResponse(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    opportunity_count: int


# ---------------------------------------------------------------------------
# Stats response
# ---------------------------------------------------------------------------


class StatsResponse(BaseModel):
    total_opportunities: int
    by_source: dict[str, int]
    by_status: dict[str, int]
    total_awards: int
    total_award_dollars: float
    closing_soon: int
    top_agencies: list[dict]


# ---------------------------------------------------------------------------
# SavedSearch (email alerts — Phase D)
# ---------------------------------------------------------------------------


class SavedSearchCreate(BaseModel):
    name: str
    query: Optional[str] = None
    agency_code: Optional[str] = None
    category: Optional[str] = None
    eligible_applicants: Optional[str] = None
    min_award: Optional[float] = None
    max_award: Optional[float] = None
    alert_email: str

    @field_validator("alert_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re

        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, v):
            raise ValueError("alert_email must be a valid email address")
        return v


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    agency_code: Optional[str] = None
    category: Optional[str] = None
    eligible_applicants: Optional[str] = None
    min_award: Optional[float] = None
    max_award: Optional[float] = None
    alert_email: Optional[str] = None

    @field_validator("alert_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re

        pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if not re.match(pattern, v):
            raise ValueError("alert_email must be a valid email address")
        return v


class SavedSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    api_key_id: int
    name: str
    query: Optional[str] = None
    agency_code: Optional[str] = None
    category: Optional[str] = None
    eligible_applicants: Optional[str] = None
    min_award: Optional[float] = None
    max_award: Optional[float] = None
    alert_email: str
    is_active: bool
    last_alerted_at: Optional[str] = None
    created_at: str


class SavedSearchList(BaseModel):
    items: list[SavedSearchResponse]
    total: int
