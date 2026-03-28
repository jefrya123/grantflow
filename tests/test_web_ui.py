"""Web UI tests for WEB-01 through WEB-04 requirements.

WEB-01: Search page has all filter inputs
WEB-02: Detail page shows historical awards table
WEB-03: Closing-soon badge on opportunities closing within 30 days
WEB-04: /stats page with totals, by-source, top agencies, closing-soon count
"""

import json
import re
from datetime import date, timedelta

from grantflow.models import Opportunity, Award


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_opp(db_session, **kwargs):
    opp_id = kwargs.get("id", "test-opp-001")
    defaults = dict(
        id=opp_id,
        source_id=f"src-{opp_id}",
        title="Test Opportunity",
        source="grants_gov",
        opportunity_status="posted",
        opportunity_number="OPP-001",
    )
    defaults.update(kwargs)
    opp = Opportunity(**defaults)
    db_session.add(opp)
    db_session.commit()
    return opp


def _make_award(db_session, opportunity_number="OPP-001", **kwargs):
    award_id = kwargs.get("id", "award-001")
    defaults = dict(
        id=award_id,
        source="usaspending",
        award_id=f"awd-{award_id}",
        opportunity_number=opportunity_number,
        recipient_name="Test Recipient",
        award_amount=50000.0,
        award_date="2024-01-15",
        place_state="CA",
        place_city="Sacramento",
    )
    defaults.update(kwargs)
    award = Award(**defaults)
    db_session.add(award)
    db_session.commit()
    return award


# ---------------------------------------------------------------------------
# WEB-01: Search filter inputs
# ---------------------------------------------------------------------------


def test_search_filter_inputs(client):
    """GET /search HTML response contains all required filter input names."""
    response = client.get("/search")
    assert response.status_code == 200
    html = response.text

    required_inputs = [
        "agency",
        "category",
        "eligible",
        "closing_after",
        "closing_before",
    ]
    for name in required_inputs:
        assert f'name="{name}"' in html, f"Missing filter input: name={name!r}"


def test_search_existing_filter_inputs(client):
    """Existing filter inputs are still present after changes."""
    response = client.get("/search")
    assert response.status_code == 200
    html = response.text

    for name in ["q", "status", "source", "min_award", "max_award"]:
        assert f'name="{name}"' in html, f"Missing existing filter input: name={name!r}"


# ---------------------------------------------------------------------------
# WEB-03: Closing-soon badge
# ---------------------------------------------------------------------------


def test_closing_soon_badge(client, db_session):
    """Opportunity closing within 30 days shows 'Closing Soon' badge."""
    close_date = (date.today() + timedelta(days=10)).isoformat()
    _make_opp(
        db_session,
        id="opp-soon",
        title="Closing Soon Opp",
        opportunity_number="OPP-SOON",
        close_date=close_date,
    )

    response = client.get("/search")
    assert response.status_code == 200
    assert "Closing Soon" in response.text


def test_closing_soon_no_badge_past(client, db_session):
    """Opportunity already closed does NOT get a closing-soon badge."""
    close_date = (date.today() - timedelta(days=5)).isoformat()
    _make_opp(
        db_session,
        id="opp-past",
        title="Past Opportunity",
        opportunity_number="OPP-PAST",
        close_date=close_date,
        opportunity_status="closed",
    )

    # Only add the past opportunity — search should not show "Closing Soon"
    response = client.get("/search?status=closed")
    assert response.status_code == 200
    assert "Closing Soon" not in response.text


# ---------------------------------------------------------------------------
# WEB-02: Detail page awards table
# ---------------------------------------------------------------------------


def test_detail_awards_section(client, db_session):
    """Detail page with linked awards renders 'Historical Awards' heading and rows."""
    _make_opp(
        db_session,
        id="opp-detail",
        title="Opp With Awards",
        opportunity_number="OPP-DETAIL",
    )
    _make_award(
        db_session,
        id="award-detail-001",
        opportunity_number="OPP-DETAIL",
        recipient_name="Acme Corp",
        award_amount=75000.0,
    )

    response = client.get("/opportunity/opp-detail")
    assert response.status_code == 200
    html = response.text
    assert "Historical Awards" in html
    assert "Acme Corp" in html


def test_detail_no_awards_section(client, db_session):
    """Detail page without awards does NOT render 'Historical Awards'."""
    _make_opp(
        db_session,
        id="opp-noaward",
        title="Opp Without Awards",
        opportunity_number="OPP-NOAWARD",
    )

    response = client.get("/opportunity/opp-noaward")
    assert response.status_code == 200
    assert "Historical Awards" not in response.text


# ---------------------------------------------------------------------------
# WEB-04: Stats page
# ---------------------------------------------------------------------------


def test_stats_page(client, db_session):
    """GET /stats returns 200 with HTML showing totals, by-source, top agencies, closing-soon."""
    # Add a couple of opportunities including one closing soon
    _make_opp(
        db_session,
        id="stats-opp-1",
        title="Stats Opp 1",
        source="grants_gov",
        agency_name="Dept of Energy",
        opportunity_number="STATS-001",
    )
    close_soon = (date.today() + timedelta(days=15)).isoformat()
    _make_opp(
        db_session,
        id="stats-opp-2",
        title="Stats Opp 2",
        source="sbir",
        agency_name="NSF",
        opportunity_number="STATS-002",
        close_date=close_soon,
    )

    response = client.get("/stats")
    assert response.status_code == 200
    html = response.text

    # Page must contain sections for all required data
    assert "Total" in html or "total" in html.lower()
    # by-source breakdown
    assert "grants_gov" in html or "sbir" in html
    # closing-soon count
    assert "Closing Soon" in html or "closing soon" in html.lower()


def test_stats_page_top_agencies(client, db_session):
    """Stats page includes a top agencies section."""
    _make_opp(
        db_session,
        id="agency-opp-1",
        title="Agency Opp 1",
        agency_name="NASA",
        opportunity_number="AGENCY-001",
    )
    _make_opp(
        db_session,
        id="agency-opp-2",
        title="Agency Opp 2",
        agency_name="NASA",
        opportunity_number="AGENCY-002",
    )

    response = client.get("/stats")
    assert response.status_code == 200
    html = response.text
    # Agency section header or the agency name itself should appear
    assert "Agency" in html or "NASA" in html


# ---------------------------------------------------------------------------
# WEB-05: Detail page SEO structured data
# ---------------------------------------------------------------------------


def test_detail_seo_jsonld(client, db_session):
    """Detail page includes JSON-LD structured data with GovernmentService type."""
    _make_opp(
        db_session,
        id="seo-opp-1",
        title="SEO Test Grant",
        description="A grant for testing SEO structured data",
        agency_name="Dept of Energy",
        agency_code="DOE",
        opportunity_number="SEO-001",
    )

    response = client.get("/opportunity/seo-opp-1")
    assert response.status_code == 200
    html = response.text
    assert "application/ld+json" in html
    assert "GovernmentService" in html
    assert "SEO Test Grant" in html


def test_detail_seo_og_tags(client, db_session):
    """Detail page includes Open Graph meta tags."""
    _make_opp(
        db_session,
        id="seo-opp-2",
        title="OG Test Grant",
        description="Grant for OG tag testing",
        opportunity_number="SEO-002",
    )

    response = client.get("/opportunity/seo-opp-2")
    assert response.status_code == 200
    html = response.text
    assert "og:title" in html
    assert "og:description" in html
    assert "og:type" in html
    assert "OG Test Grant" in html


def test_detail_seo_twitter_card(client, db_session):
    """Detail page includes Twitter Card meta tags."""
    _make_opp(
        db_session,
        id="seo-opp-3",
        title="Twitter Test Grant",
        opportunity_number="SEO-003",
    )

    response = client.get("/opportunity/seo-opp-3")
    assert response.status_code == 200
    html = response.text
    assert "twitter:card" in html
    assert "twitter:title" in html


def test_detail_seo_includes_agency(client, db_session):
    """JSON-LD includes agency as serviceOperator when present."""
    _make_opp(
        db_session,
        id="seo-opp-4",
        title="Agency SEO Grant",
        agency_name="National Science Foundation",
        opportunity_number="SEO-004",
    )

    response = client.get("/opportunity/seo-opp-4")
    assert response.status_code == 200
    html = response.text
    assert "National Science Foundation" in html
    assert "GovernmentOrganization" in html


def test_detail_seo_jsonld_dates(client, db_session):
    """JSON-LD includes datePosted and availableThrough when dates are present."""
    _make_opp(
        db_session,
        id="seo-opp-5",
        title="Date SEO Grant",
        post_date="2024-01-01",
        close_date="2024-12-31",
        opportunity_number="SEO-005",
    )

    response = client.get("/opportunity/seo-opp-5")
    assert response.status_code == 200
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL
    )
    assert match, "No JSON-LD script block found"
    ld = json.loads(match.group(1))
    assert ld.get("datePosted") == "2024-01-01"
    assert ld.get("availableThrough") == "2024-12-31"


def test_detail_seo_jsonld_amount(client, db_session):
    """JSON-LD includes award_ceiling as an Offer when present."""
    _make_opp(
        db_session,
        id="seo-opp-6",
        title="Amount SEO Grant",
        award_ceiling=500000.0,
        opportunity_number="SEO-006",
    )

    response = client.get("/opportunity/seo-opp-6")
    assert response.status_code == 200
    match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL
    )
    assert match, "No JSON-LD script block found"
    ld = json.loads(match.group(1))
    assert "offers" in ld
    assert ld["offers"]["price"] == 500000.0
    assert ld["offers"]["priceCurrency"] == "USD"


# ---------------------------------------------------------------------------
# WEB-01 extension: Nav bar
# ---------------------------------------------------------------------------


def test_nav_stats_link(client):
    """Search page nav contains link to /stats (not /api/v1/stats)."""
    response = client.get("/search")
    assert response.status_code == 200
    html = response.text
    assert 'href="/stats"' in html
    # Must NOT link to JSON API
    assert 'href="/api/v1/stats"' not in html
