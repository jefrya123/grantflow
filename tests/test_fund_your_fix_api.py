"""Tests for GET /api/v1/fund-your-fix — JSON API for ComplianceGrade integration."""

from grantflow.models import Opportunity


def _make_ada_opp(
    db_session, opp_id, title="ADA Test Grant", close_date=None, **kwargs
):
    defaults = dict(
        id=opp_id,
        source_id=f"src-{opp_id}",
        title=title,
        source="grants_gov",
        opportunity_status="posted",
        opportunity_number=f"ADA-{opp_id}",
        topic_tags='["ada-compliance", "transportation"]',
        agency_name="Dept of Transportation",
        source_url=f"https://grants.gov/opp/{opp_id}",
    )
    if close_date:
        defaults["close_date"] = close_date
    defaults.update(kwargs)
    opp = Opportunity(**defaults)
    db_session.add(opp)
    db_session.commit()
    return opp


def test_fund_your_fix_api_returns_json(client, db_session):
    """GET /api/v1/fund-your-fix returns 200 JSON with grants array."""
    _make_ada_opp(db_session, "api-001", title="ADA API Grant One")
    response = client.get("/api/v1/fund-your-fix")
    assert response.status_code == 200
    data = response.json()
    assert "grants" in data
    assert isinstance(data["grants"], list)
    assert "total" in data


def test_fund_your_fix_api_response_schema(client, db_session):
    """Each grant in response has required fields."""
    _make_ada_opp(
        db_session,
        "api-schema-001",
        title="Schema Test Grant",
        award_floor=10000.0,
        award_ceiling=500000.0,
    )
    response = client.get("/api/v1/fund-your-fix")
    assert response.status_code == 200
    grants = response.json()["grants"]
    assert len(grants) >= 1
    g = grants[0]
    for field in (
        "id",
        "title",
        "agency",
        "close_date",
        "award_floor",
        "award_ceiling",
        "url",
        "source",
    ):
        assert field in g, f"Missing field: {field}"


def test_fund_your_fix_api_excludes_expired(client, db_session):
    """Expired grants (close_date in the past) are not returned."""
    _make_ada_opp(
        db_session,
        "api-expired-001",
        title="Expired ADA Grant",
        close_date="2020-01-01",
    )
    _make_ada_opp(
        db_session, "api-active-001", title="Active ADA Grant", close_date="2099-12-31"
    )
    response = client.get("/api/v1/fund-your-fix")
    assert response.status_code == 200
    titles = [g["title"] for g in response.json()["grants"]]
    assert "Expired ADA Grant" not in titles
    assert "Active ADA Grant" in titles


def test_fund_your_fix_api_municipality_filter(client, db_session):
    """?municipality=boston narrows results to matching grants."""
    _make_ada_opp(
        db_session,
        "api-muni-001",
        title="Boston ADA Grant",
        eligible_applicants="City of Boston, MA",
    )
    _make_ada_opp(
        db_session,
        "api-muni-002",
        title="Chicago ADA Grant",
        eligible_applicants="City of Chicago, IL",
    )
    response = client.get("/api/v1/fund-your-fix?municipality=boston")
    assert response.status_code == 200
    data = response.json()
    assert data["municipality"] == "boston"
    titles = [g["title"] for g in data["grants"]]
    assert "Boston ADA Grant" in titles
    assert "Chicago ADA Grant" not in titles


def test_fund_your_fix_api_limit_param(client, db_session):
    """?limit=2 returns at most 2 grants."""
    for i in range(5):
        _make_ada_opp(db_session, f"api-lim-{i:03d}", title=f"ADA Limit Grant {i}")
    response = client.get("/api/v1/fund-your-fix?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["grants"]) <= 2


def test_fund_your_fix_api_total_matches_db(client, db_session):
    """Response total matches number of ADA grants in DB."""
    for i in range(3):
        _make_ada_opp(db_session, f"api-tot-{i:03d}", title=f"ADA Total Grant {i}")
    response = client.get("/api/v1/fund-your-fix?limit=50")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(data["grants"])


def test_fund_your_fix_api_no_auth_required(client):
    """Endpoint returns 200 without any API key."""
    response = client.get("/api/v1/fund-your-fix")
    assert response.status_code == 200
