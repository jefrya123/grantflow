"""
Tests for the agencies endpoint and AgencyResponse schema (API-08).

Covers:
  - AgencyResponse Pydantic model validation
  - GET /api/v1/agencies returns list with code, name, opportunity_count
  - Response objects conform to AgencyResponse schema
"""

import datetime
import hashlib

import pytest
from pydantic import ValidationError

from grantflow.api.schemas import AgencyResponse
from grantflow.models import ApiKey, Opportunity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def make_key(db, tier: str = "free", key_suffix: str = "") -> str:
    plaintext = f"agencies_testkey_{tier}{key_suffix}"
    row = ApiKey(
        key_hash=_hash(plaintext),
        key_prefix=plaintext[:8],
        tier=tier,
        is_active=True,
        created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        last_used_at=None,
        request_count=0,
    )
    db.add(row)
    db.commit()
    return plaintext


def make_opportunity(
    db, agency_code: str, agency_name: str, idx: int = 0
) -> Opportunity:
    opp = Opportunity(
        id=f"opp-agency-{agency_code}-{idx}",
        source="agencies_test",
        source_id=f"AT-{agency_code}-{idx}",
        title=f"Agency Test Grant {agency_code}-{idx}",
        agency_code=agency_code,
        agency_name=agency_name,
        opportunity_status="posted",
    )
    db.add(opp)
    db.commit()
    return opp


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------


def test_agency_schema_valid():
    """AgencyResponse validates correctly with all fields."""
    agency = AgencyResponse(code="DOE", name="Dept of Energy", opportunity_count=5)
    assert agency.code == "DOE"
    assert agency.name == "Dept of Energy"
    assert agency.opportunity_count == 5


def test_agency_schema_optional_code():
    """AgencyResponse allows code=None (some agencies lack a code)."""
    agency = AgencyResponse(code=None, name="Unknown Agency", opportunity_count=1)
    assert agency.code is None


def test_agency_schema_optional_name():
    """AgencyResponse allows name=None."""
    agency = AgencyResponse(code="XYZ", name=None, opportunity_count=3)
    assert agency.name is None


def test_agency_schema_opportunity_count_required():
    """AgencyResponse raises ValidationError when opportunity_count is missing."""
    with pytest.raises(ValidationError):
        AgencyResponse(code="DOE", name="Dept of Energy")


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------


def test_agencies_endpoint_returns_list(client, db_session):
    """GET /api/v1/agencies with valid key returns a non-empty JSON list."""
    key = make_key(db_session)
    make_opportunity(db_session, "HHS", "Dept of Health")

    resp = client.get("/api/v1/agencies", headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_agencies_endpoint_response_shape(client, db_session):
    """Each object in the agencies response has code, name, opportunity_count."""
    key = make_key(db_session, key_suffix="_shape")
    make_opportunity(db_session, "NSF", "National Science Foundation")

    resp = client.get("/api/v1/agencies", headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()

    for item in data:
        assert "code" in item, f"Missing 'code' in {item}"
        assert "name" in item, f"Missing 'name' in {item}"
        assert "opportunity_count" in item, f"Missing 'opportunity_count' in {item}"


def test_agencies_response_conforms_to_schema(client, db_session):
    """Every agencies response item validates against AgencyResponse schema."""
    key = make_key(db_session, key_suffix="_schema")
    make_opportunity(db_session, "NIH", "National Institutes of Health")

    resp = client.get("/api/v1/agencies", headers={"X-API-Key": key})
    assert resp.status_code == 200

    for item in resp.json():
        # Should not raise
        agency = AgencyResponse(**item)
        assert isinstance(agency.opportunity_count, int)


def test_agencies_endpoint_no_extra_fields(client, db_session):
    """Agencies response does not include unexpected extra fields."""
    key = make_key(db_session, key_suffix="_extra")
    make_opportunity(db_session, "DOT", "Dept of Transportation")

    resp = client.get("/api/v1/agencies", headers={"X-API-Key": key})
    assert resp.status_code == 200

    allowed_fields = {"code", "name", "opportunity_count"}
    for item in resp.json():
        extra = set(item.keys()) - allowed_fields
        assert not extra, f"Unexpected extra fields in response: {extra}"
