"""
Schema contract tests — field presence and types.
Verifies that Pydantic response models enforce the stable API contract.
"""
import datetime
import hashlib

import pytest
from grantflow.api.schemas import (
    OpportunityResponse,
    AwardResponse,
    OpportunityDetailResponse,
    SearchResponse,
    KeyCreateResponse,
    StatsResponse,
)
from grantflow.models import Opportunity, Award, ApiKey


# ---------------------------------------------------------------------------
# Helpers (used by linked-awards integration test)
# ---------------------------------------------------------------------------

def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _make_key(db, suffix: str = "") -> str:
    plaintext = f"schemas_testkey{suffix}"
    row = ApiKey(
        key_hash=_hash(plaintext),
        key_prefix=plaintext[:8],
        tier="free",
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        last_used_at=None,
        request_count=0,
    )
    db.add(row)
    db.commit()
    return plaintext


# ---------------------------------------------------------------------------
# Fixtures: minimal dicts matching the exact shapes from _opportunity_to_dict
# ---------------------------------------------------------------------------

OPPORTUNITY_DICT = {
    "id": "abc-123",
    "source": "grants_gov",
    "source_id": "GG-001",
    "title": "Test Grant",
    "description": "A test grant opportunity",
    "agency_code": "HHS",
    "agency_name": "Dept of Health",
    "opportunity_number": "HHS-2024-001",
    "opportunity_status": "posted",
    "funding_instrument": "grant",
    "category": "health",
    "cfda_numbers": "93.001",
    "eligible_applicants": '["nonprofits", "states"]',
    "post_date": "2024-01-01",
    "close_date": "2024-03-01",
    "last_updated": "2024-01-15",
    "award_floor": 10000.0,
    "award_ceiling": 500000.0,
    "estimated_total_funding": 1000000.0,
    "expected_number_of_awards": 5,
    "cost_sharing_required": False,
    "contact_email": "grants@hhs.gov",
    "contact_text": "Call us",
    "additional_info_url": "https://hhs.gov/info",
    "source_url": "https://grants.gov/opp/123",
}

AWARD_DICT = {
    "id": "awd-456",
    "award_id": "AWD-2024-456",
    "title": "Test Award",
    "recipient_name": "Nonprofit Org",
    "award_amount": 250000.0,
    "award_date": "2024-02-01",
    "agency_name": "Dept of Health",
    "place_state": "CA",
    "place_city": "Sacramento",
}


# ---------------------------------------------------------------------------
# OpportunityResponse tests
# ---------------------------------------------------------------------------

def test_opportunity_response_from_dict():
    """OpportunityResponse can be instantiated from a dict with all expected keys."""
    opp = OpportunityResponse.model_validate(OPPORTUNITY_DICT)
    assert opp.id == "abc-123"
    assert opp.source == "grants_gov"
    assert opp.title == "Test Grant"
    assert opp.award_ceiling == 500000.0
    assert opp.cost_sharing_required is False


def test_opportunity_response_required_fields_present():
    """Required fields (id, source, source_id, title) must be present."""
    opp = OpportunityResponse(**OPPORTUNITY_DICT)
    assert opp.id is not None
    assert opp.source is not None
    assert opp.source_id is not None
    assert opp.title is not None


def test_opportunity_response_optional_fields_default_to_none():
    """Missing optional fields default to None — no KeyError."""
    minimal = {"id": "x1", "source": "grants_gov", "source_id": "GG-X1", "title": "Minimal"}
    opp = OpportunityResponse.model_validate(minimal)
    assert opp.description is None
    assert opp.agency_code is None
    assert opp.award_ceiling is None
    assert opp.close_date is None
    assert opp.cost_sharing_required is None


def test_opportunity_response_preserves_exact_field_names():
    """Field names must exactly match the stable API contract."""
    opp = OpportunityResponse(**OPPORTUNITY_DICT)
    serialized = opp.model_dump()
    expected_keys = {
        "id", "source", "source_id", "title", "description", "agency_code",
        "agency_name", "opportunity_number", "opportunity_status", "funding_instrument",
        "category", "cfda_numbers", "eligible_applicants", "post_date", "close_date",
        "last_updated", "award_floor", "award_ceiling", "estimated_total_funding",
        "expected_number_of_awards", "cost_sharing_required", "contact_email",
        "contact_text", "additional_info_url", "source_url",
        "topic_tags",
    }
    assert set(serialized.keys()) == expected_keys


# ---------------------------------------------------------------------------
# AwardResponse tests
# ---------------------------------------------------------------------------

def test_award_response_from_dict():
    """AwardResponse can be instantiated from a dict."""
    award = AwardResponse.model_validate(AWARD_DICT)
    assert award.id == "awd-456"
    assert award.award_id == "AWD-2024-456"
    assert award.award_amount == 250000.0


def test_award_response_from_attributes_enabled():
    """AwardResponse model_config enables from_attributes=True (ORM usage)."""
    # Simulate an ORM-like object with attributes
    class FakeAward:
        id = "awd-789"
        award_id = "AWD-789"
        title = "ORM Award"
        recipient_name = "Test Org"
        award_amount = 100000.0
        award_date = "2024-03-01"
        agency_name = "NSF"
        place_state = "DC"
        place_city = "Washington"

    award = AwardResponse.model_validate(FakeAward())
    assert award.id == "awd-789"
    assert award.award_amount == 100000.0


def test_award_response_optional_fields_default_to_none():
    """Missing optional award fields default to None."""
    minimal = {"id": "awd-min", "award_id": "AWD-MIN"}
    award = AwardResponse.model_validate(minimal)
    assert award.title is None
    assert award.recipient_name is None
    assert award.award_amount is None


# ---------------------------------------------------------------------------
# OpportunityDetailResponse tests
# ---------------------------------------------------------------------------

def test_opportunity_detail_response_includes_awards():
    """OpportunityDetailResponse extends OpportunityResponse with awards list."""
    detail = OpportunityDetailResponse.model_validate(OPPORTUNITY_DICT)
    assert hasattr(detail, "awards")
    assert isinstance(detail.awards, list)
    assert detail.awards == []  # default empty


def test_opportunity_detail_response_with_awards():
    """OpportunityDetailResponse awards list can contain AwardResponse objects."""
    detail = OpportunityDetailResponse.model_validate(OPPORTUNITY_DICT)
    detail.awards = [AwardResponse.model_validate(AWARD_DICT)]
    assert len(detail.awards) == 1
    assert detail.awards[0].award_id == "AWD-2024-456"


# ---------------------------------------------------------------------------
# SearchResponse tests
# ---------------------------------------------------------------------------

def test_search_response_serializes_correctly():
    """SearchResponse serializes to the correct JSON shape."""
    opp = OpportunityResponse.model_validate(OPPORTUNITY_DICT)
    search = SearchResponse(
        results=[opp],
        total=1,
        page=1,
        per_page=20,
        pages=1,
    )
    serialized = search.model_dump()
    assert serialized["total"] == 1
    assert serialized["page"] == 1
    assert serialized["per_page"] == 20
    assert serialized["pages"] == 1
    assert len(serialized["results"]) == 1
    assert serialized["results"][0]["id"] == "abc-123"


def test_search_response_empty_results():
    """SearchResponse with no results is valid."""
    search = SearchResponse(results=[], total=0, page=1, per_page=20, pages=1)
    assert search.results == []
    assert search.total == 0


# ---------------------------------------------------------------------------
# KeyCreateResponse tests
# ---------------------------------------------------------------------------

def test_key_create_response_fields():
    """KeyCreateResponse has key, key_prefix, tier, created_at fields."""
    resp = KeyCreateResponse(
        key="gf_live_abc123",
        key_prefix="gf_live_",
        tier="free",
        created_at="2024-01-01T00:00:00Z",
    )
    assert resp.key == "gf_live_abc123"
    assert resp.key_prefix == "gf_live_"
    assert resp.tier == "free"
    assert resp.created_at == "2024-01-01T00:00:00Z"


# ---------------------------------------------------------------------------
# StatsResponse tests
# ---------------------------------------------------------------------------

def test_stats_response_fields():
    """StatsResponse has all required stats fields."""
    stats = StatsResponse(
        total_opportunities=100,
        by_source={"grants_gov": 80, "sam_gov": 20},
        by_status={"posted": 60, "closed": 40},
        total_awards=50,
        total_award_dollars=5000000.0,
        closing_soon=10,
        top_agencies=[{"agency": "HHS", "count": 30}],
    )
    assert stats.total_opportunities == 100
    assert stats.by_source["grants_gov"] == 80
    assert stats.total_award_dollars == 5000000.0
    assert len(stats.top_agencies) == 1


# ---------------------------------------------------------------------------
# Linked awards integration test (API-06)
# ---------------------------------------------------------------------------

def test_opportunity_detail_awards(client, db_session):
    """GET /api/v1/opportunities/{id} returns non-empty awards list with AwardResponse fields."""
    key = _make_key(db_session, suffix="_awards")

    # Create an opportunity with a known opportunity_number
    opp = Opportunity(
        id="opp-linked-award-test",
        source="schemas_test",
        source_id="ST-LINKED-001",
        title="Linked Award Test Grant",
        opportunity_number="SCHEMAS-TEST-001",
        opportunity_status="posted",
        agency_code="NSF",
        agency_name="National Science Foundation",
    )
    db_session.add(opp)

    # Create an award linked by opportunity_number
    award = Award(
        id="award-linked-test-001",
        source="usaspending",
        award_id="USA-LINKED-001",
        title="Linked Test Award",
        recipient_name="Test Nonprofit",
        award_amount=150000.0,
        award_date="2024-06-01",
        agency_name="National Science Foundation",
        opportunity_number="SCHEMAS-TEST-001",
    )
    db_session.add(award)
    db_session.commit()

    resp = client.get(
        "/api/v1/opportunities/opp-linked-award-test",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "awards" in data, "Detail response must include 'awards' field"
    assert len(data["awards"]) >= 1, "Must return at least one linked award"

    aw = data["awards"][0]
    # Verify AwardResponse fields are present
    assert "id" in aw
    assert "recipient_name" in aw
    assert "award_amount" in aw
    assert aw["recipient_name"] == "Test Nonprofit"
    assert aw["award_amount"] == 150000.0
