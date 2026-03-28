"""Tests for /agency/{slug} SEO page."""

from grantflow.models import Opportunity


def _make_opp(db_session, **kwargs):
    opp_id = kwargs.get("id", "test-opp-001")
    defaults = dict(
        id=opp_id,
        source_id=f"src-{opp_id}",
        title="Test Opportunity",
        source="agency_test",
        opportunity_status="posted",
        opportunity_number="OPP-001",
    )
    defaults.update(kwargs)
    opp = Opportunity(**defaults)
    db_session.add(opp)
    db_session.commit()
    return opp


def test_agency_page_found(client, db_session):
    _make_opp(
        db_session,
        id="ag-1",
        title="NASA Grant A",
        agency_code="NASA",
        agency_name="National Aeronautics and Space Administration",
    )
    _make_opp(
        db_session,
        id="ag-2",
        title="NASA Grant B",
        agency_code="NASA",
        agency_name="National Aeronautics and Space Administration",
    )

    response = client.get("/agency/NASA")
    assert response.status_code == 200
    text = response.text
    assert "National Aeronautics and Space Administration" in text
    assert "NASA Grant A" in text
    assert "NASA Grant B" in text


def test_agency_page_case_insensitive(client, db_session):
    _make_opp(
        db_session,
        id="ag-ci-1",
        title="DOE Grant",
        agency_code="DOE",
        agency_name="Dept of Energy",
    )

    response = client.get("/agency/doe")
    assert response.status_code == 200
    assert "Dept of Energy" in response.text


def test_agency_page_not_found(client, db_session):
    response = client.get("/agency/ZZZUNKNOWN")
    assert response.status_code == 404


def test_agency_page_seo_meta(client, db_session):
    _make_opp(
        db_session,
        id="ag-seo-1",
        title="HHS Grant",
        agency_code="HHS",
        agency_name="Dept of Health and Human Services",
    )

    response = client.get("/agency/HHS")
    assert response.status_code == 200
    text = response.text
    assert "application/ld+json" in text
    assert "GovernmentOrganization" in text
    assert "og:title" in text
    assert "og:description" in text


def test_agency_page_pagination(client, db_session):
    for i in range(5):
        _make_opp(
            db_session,
            id=f"ag-pg-{i}",
            title=f"NSF Grant {i}",
            agency_code="NSF",
            agency_name="National Science Foundation",
        )

    response = client.get("/agency/NSF?per_page=2&page=1")
    assert response.status_code == 200
    assert "Page 1 of 3" in response.text
