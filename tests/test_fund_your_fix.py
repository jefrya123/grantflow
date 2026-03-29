"""Tests for /fund-your-fix page — ADA compliance grant discovery."""

import json
import re

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
    )
    if close_date:
        defaults["close_date"] = close_date
    defaults.update(kwargs)
    opp = Opportunity(**defaults)
    db_session.add(opp)
    db_session.commit()
    return opp


def test_fund_your_fix_returns_200(client):
    """GET /fund-your-fix returns HTTP 200."""
    response = client.get("/fund-your-fix")
    assert response.status_code == 200


def test_fund_your_fix_contains_heading(client):
    """Page contains 'Fund Your Fix' heading."""
    response = client.get("/fund-your-fix")
    assert response.status_code == 200
    assert "Fund Your Fix" in response.text


def test_fund_your_fix_shows_ada_grants(client, db_session):
    """Page shows ADA compliance grants from the database."""
    _make_ada_opp(db_session, "ada-001", title="All Stations Accessibility Program")
    _make_ada_opp(db_session, "ada-002", title="ADA Transition Plan Grants")

    response = client.get("/fund-your-fix")
    assert response.status_code == 200
    html = response.text
    assert "All Stations Accessibility Program" in html
    assert "ADA Transition Plan Grants" in html


def test_fund_your_fix_pagination(client, db_session):
    """Page=2 returns a valid 200 response (pagination works)."""
    # Create 25 ADA grants so there's a second page at per_page=20
    for i in range(25):
        _make_ada_opp(db_session, f"ada-page-{i:03d}", title=f"ADA Grant {i:03d}")

    response = client.get("/fund-your-fix?page=2")
    assert response.status_code == 200
    assert "Fund Your Fix" in response.text


def test_fund_your_fix_jsonld_present(client, db_session):
    """Page includes JSON-LD structured data (ItemList schema)."""
    _make_ada_opp(db_session, "ada-ld-001", title="ADA Accessibility Grant")

    response = client.get("/fund-your-fix")
    assert response.status_code == 200
    html = response.text
    assert "application/ld+json" in html
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    assert match, "No JSON-LD script block found"
    ld = json.loads(match.group(1))
    assert ld.get("@type") == "ItemList"
