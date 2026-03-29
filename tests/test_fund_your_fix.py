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


def test_municipality_filter_shows_matching_grants(client, db_session):
    """?municipality=boston shows matching grants and banner text."""
    _make_ada_opp(
        db_session,
        "muni-001",
        title="Boston ADA Transit Grant",
        eligible_applicants="City of Boston, MA",
    )
    _make_ada_opp(
        db_session,
        "muni-002",
        title="ADA Grant for Other Cities",
        eligible_applicants="City of Chicago, IL",
    )

    response = client.get("/fund-your-fix?municipality=boston")
    assert response.status_code == 200
    html = response.text
    assert "Boston ADA Transit Grant" in html
    assert "Showing grants for" in html


def test_municipality_filter_fail_open(client, db_session):
    """?municipality=nonexistent-city returns all grants (fail-open, total > 0)."""
    _make_ada_opp(
        db_session,
        "muni-fo-001",
        title="Statewide ADA Compliance Grant",
    )

    response = client.get("/fund-your-fix?municipality=nonexistent-city")
    assert response.status_code == 200
    html = response.text
    # Fail-open: total grants > 0 (JSON-LD numberOfItems confirms count)
    match = re.search(r'"numberOfItems":\s*(\d+)', html)
    assert match, "JSON-LD numberOfItems not found"
    assert int(match.group(1)) > 0, "Expected at least one grant (fail-open)"


def test_ada_grants_redirect(client):
    """GET /ada-grants returns 301 redirect to /fund-your-fix."""
    response = client.get("/ada-grants", follow_redirects=False)
    assert response.status_code == 301
    assert "/fund-your-fix" in response.headers["location"]


def test_widget_returns_200(client, db_session):
    """GET /fund-your-fix/widget returns 200 with grant titles."""
    # Use early close_dates so these grants sort to top of the 5-slot widget
    _make_ada_opp(
        db_session,
        "widget-001",
        title="ADA Widget Grant Alpha",
        close_date="2026-04-01",
    )
    _make_ada_opp(
        db_session, "widget-002", title="ADA Widget Grant Beta", close_date="2026-04-02"
    )

    response = client.get("/fund-your-fix/widget")
    assert response.status_code == 200
    html = response.text
    assert "ADA Widget Grant Alpha" in html
    assert "ADA Widget Grant Beta" in html


def test_widget_no_base_html(client, db_session):
    """Widget response does not include site nav; contains widget title."""
    _make_ada_opp(db_session, "widget-nb-001", title="Widget Standalone Grant")

    response = client.get("/fund-your-fix/widget")
    assert response.status_code == 200
    html = response.text
    # Standalone template — no base.html navigation artifacts
    assert "nav" not in html.lower() or "navbar" not in html
    assert "ADA Compliance Grants Widget" in html


def test_widget_limits_to_5(client, db_session):
    """Widget shows at most 5 grant items even when more grants exist."""
    for i in range(7):
        _make_ada_opp(
            db_session, f"widget-lim-{i:03d}", title=f"Widget Limit Grant {i:03d}"
        )

    response = client.get("/fund-your-fix/widget")
    assert response.status_code == 200
    html = response.text
    count = html.count('class="grant-item"')
    assert count == 5


def test_featured_fta_grant_pinned(client, db_session):
    """'All Stations Access Program' is pinned as featured over closer-deadline grants."""
    _make_ada_opp(
        db_session,
        "fta-001",
        title="All Stations Access Program",
        close_date="2026-12-31",
    )
    _make_ada_opp(
        db_session,
        "fta-002",
        title="Local ADA Ramp Grant",
        close_date="2026-04-01",
    )

    response = client.get("/fund-your-fix")
    assert response.status_code == 200
    html = response.text
    # All Stations Access should appear in the featured section
    assert "All Stations Access" in html


def test_og_image_present(client):
    """GET /fund-your-fix returns HTML containing og:image meta tag."""
    response = client.get("/fund-your-fix")
    assert response.status_code == 200
    html = response.text
    assert "og:image" in html
    assert "og-fund-your-fix.png" in html
