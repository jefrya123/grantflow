"""Unit tests for ADA keyword matching and backfill logic."""

import json
from sqlalchemy import text

from grantflow.pipeline.ada_tagger import (
    _is_ada_match,
    _parse_tags,
    run_ada_backfill,
)


# ---------------------------------------------------------------------------
# Keyword matching — True cases
# ---------------------------------------------------------------------------


class TestKeywordMatchingTrue:
    def test_americans_with_disabilities_act_in_title(self):
        assert (
            _is_ada_match("Americans with Disabilities Act Grant", None, None) is True
        )

    def test_ada_compliance_in_title(self):
        assert (
            _is_ada_match("ADA Compliance Infrastructure Program", None, None) is True
        )

    def test_federal_transit_administration_in_agency(self):
        assert _is_ada_match(None, None, "Federal Transit Administration") is True

    def test_paratransit_in_description(self):
        assert (
            _is_ada_match(
                None, "This grant funds paratransit services for riders", None
            )
            is True
        )

    def test_all_stations_accessibility_in_title(self):
        assert _is_ada_match("All Stations Accessibility Program", None, None) is True

    def test_section_504_in_description(self):
        assert (
            _is_ada_match(
                None, "Compliance with Section 504 of the Rehabilitation Act", None
            )
            is True
        )

    def test_wheelchair_in_title(self):
        assert (
            _is_ada_match("Wheelchair Accessible Station Improvements", None, None)
            is True
        )

    def test_curb_cut_in_description(self):
        assert (
            _is_ada_match(
                None, "Funding for curb cut installation at intersections", None
            )
            is True
        )


# ---------------------------------------------------------------------------
# Keyword matching — False cases (false positive prevention)
# ---------------------------------------------------------------------------


class TestKeywordMatchingFalse:
    def test_adaptation_program_bare_ada_substring_in_title(self):
        """'ADAPTATION' contains 'ada' as substring — must NOT match."""
        assert (
            _is_ada_match("ADAPTATION program for rural communities", None, None)
            is False
        )

    def test_adams_county_in_title(self):
        """'Adams' contains 'ada' as substring — must NOT match."""
        assert (
            _is_ada_match("Adams County Rural Development Grant", None, None) is False
        )

    def test_nadac_pricing_in_title(self):
        """'NADAC' contains 'ada' as substring — must NOT match."""
        assert _is_ada_match("NADAC Pricing Initiative", None, None) is False

    def test_academic_in_description(self):
        """'academic' contains 'ada' as substring — must NOT match."""
        assert (
            _is_ada_match(None, "Support for academic research programs", None) is False
        )

    def test_empty_strings(self):
        assert _is_ada_match("", "", "") is False

    def test_none_fields(self):
        assert _is_ada_match(None, None, None) is False


# ---------------------------------------------------------------------------
# _parse_tags
# ---------------------------------------------------------------------------


class TestParseTags:
    def test_parse_tags_none(self):
        assert _parse_tags(None) == []

    def test_parse_tags_valid(self):
        assert _parse_tags('["health", "research"]') == ["health", "research"]

    def test_parse_tags_malformed(self):
        assert _parse_tags("not json{") == []

    def test_parse_tags_non_list(self):
        assert _parse_tags('"just a string"') == []


# ---------------------------------------------------------------------------
# Backfill integration tests (use db_session fixture)
# ---------------------------------------------------------------------------


class TestBackfill:
    def _insert_row(
        self,
        db_session,
        row_id,
        title,
        description=None,
        agency_name=None,
        topic_tags=None,
        source="test",
    ):
        db_session.execute(
            text(
                "INSERT INTO opportunities "
                "(id, title, description, agency_name, topic_tags, source, source_id) "
                "VALUES (:id, :title, :desc, :agency, :tags, :src, :src_id)"
            ),
            {
                "id": row_id,
                "title": title,
                "desc": description,
                "agency": agency_name,
                "tags": topic_tags,
                "src": source,
                "src_id": row_id,
            },
        )
        db_session.flush()

    def test_backfill_tags_matching_records(self, db_session):
        """Exactly 2 of 3 rows should be tagged."""
        self._insert_row(db_session, "back-1", "ADA Compliance Sidewalk Grant")
        self._insert_row(
            db_session,
            "back-2",
            "Rural Roads Program",
            agency_name="Federal Transit Administration",
        )
        self._insert_row(db_session, "back-3", "Agricultural Research Initiative")

        count = run_ada_backfill(db=db_session)
        assert count == 2

        row1 = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'back-1'")
        ).fetchone()
        row3 = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'back-3'")
        ).fetchone()

        assert "ada-compliance" in json.loads(row1[0])
        assert row3[0] is None

    def test_backfill_idempotent(self, db_session):
        """Running backfill twice should not duplicate the tag."""
        self._insert_row(
            db_session, "idem-1", "Wheelchair Accessible Transit Improvements"
        )

        run_ada_backfill(db=db_session)
        # Reset session state so second call sees committed data
        db_session.flush()
        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'idem-1'")
        ).fetchone()
        tags = json.loads(row[0])
        assert tags.count("ada-compliance") == 1

    def test_backfill_preserves_existing_tags(self, db_session):
        """Existing tags must not be wiped; ada-compliance appended."""
        self._insert_row(
            db_session,
            "pres-1",
            "Curb Cut Accessibility Program",
            topic_tags='["health"]',
        )

        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'pres-1'")
        ).fetchone()
        tags = json.loads(row[0])
        assert "health" in tags
        assert "ada-compliance" in tags

    def test_backfill_malformed_tags(self, db_session):
        """Malformed topic_tags JSON should be recovered gracefully."""
        self._insert_row(
            db_session,
            "mal-1",
            "All Stations Accessibility Infrastructure",
            topic_tags="broken{json",
        )

        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'mal-1'")
        ).fetchone()
        tags = json.loads(row[0])
        assert tags == ["ada-compliance"]


# ---------------------------------------------------------------------------
# Integration tests for GET /api/v1/opportunities/ada-compliance endpoint
# ---------------------------------------------------------------------------


def _insert_opportunity(
    db_session,
    row_id,
    title="Test Grant",
    topic_tags=None,
    description=None,
    close_date=None,
    award_floor=None,
    award_ceiling=None,
    source="grants_gov",
    source_url=None,
    canonical_id=None,
    eligible_applicants=None,
):
    """Helper to insert a minimal opportunity row for endpoint tests."""
    db_session.execute(
        text(
            "INSERT INTO opportunities "
            "(id, title, description, topic_tags, close_date, award_floor, award_ceiling, "
            "source, source_id, source_url, canonical_id, eligible_applicants) "
            "VALUES (:id, :title, :desc, :tags, :close_date, :award_floor, :award_ceiling, "
            ":source, :source_id, :source_url, :canonical_id, :eligible_applicants)"
        ),
        {
            "id": row_id,
            "title": title,
            "desc": description,
            "tags": topic_tags,
            "close_date": close_date,
            "award_floor": award_floor,
            "award_ceiling": award_ceiling,
            "source": source,
            "source_id": row_id,
            "source_url": source_url,
            "canonical_id": canonical_id,
            "eligible_applicants": eligible_applicants,
        },
    )
    db_session.flush()


class TestAdaComplianceEndpoint:
    def test_endpoint_returns_200(self, client, db_session):
        _insert_opportunity(db_session, "ep-1", topic_tags='["ada-compliance"]')
        response = client.get("/api/v1/opportunities/ada-compliance")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert isinstance(data["results"], list)

    def test_endpoint_response_fields(self, client, db_session):
        _insert_opportunity(
            db_session,
            "ep-2",
            title="Test ADA Grant",
            topic_tags='["ada-compliance"]',
            close_date="2026-05-01",
            award_floor=100000,
            award_ceiling=500000,
            source="grants_gov",
            source_url="https://example.com",
            canonical_id="canon_abc123",
        )
        response = client.get("/api/v1/opportunities/ada-compliance")
        assert response.status_code == 200
        results = response.json()["results"]
        # Find our inserted grant
        match = next((r for r in results if r["id"] == "ep-2"), None)
        assert match is not None
        assert match["title"] == "Test ADA Grant"
        assert match["close_date"] == "2026-05-01"
        assert match["award_floor"] == 100000
        assert match["award_ceiling"] == 500000
        assert match["source"] == "grants_gov"
        assert match["source_url"] == "https://example.com"
        assert match["canonical_id"] == "canon_abc123"

    def test_endpoint_sort_order(self, client, db_session):
        _insert_opportunity(
            db_session,
            "sort-1",
            topic_tags='["ada-compliance"]',
            close_date="2026-06-01",
        )
        _insert_opportunity(
            db_session,
            "sort-2",
            topic_tags='["ada-compliance"]',
            close_date="2026-05-01",
        )
        _insert_opportunity(
            db_session, "sort-3", topic_tags='["ada-compliance"]', close_date=None
        )

        response = client.get("/api/v1/opportunities/ada-compliance")
        assert response.status_code == 200
        results = response.json()["results"]

        # Find positions of our three test rows
        ids = [r["id"] for r in results]
        idx_sort1 = ids.index("sort-1") if "sort-1" in ids else None
        idx_sort2 = ids.index("sort-2") if "sort-2" in ids else None
        idx_sort3 = ids.index("sort-3") if "sort-3" in ids else None

        assert idx_sort2 is not None and idx_sort1 is not None and idx_sort3 is not None
        # sort-2 (May) before sort-1 (June) before sort-3 (None/last)
        assert idx_sort2 < idx_sort1
        assert idx_sort1 < idx_sort3

    def test_endpoint_pagination(self, client, db_session):
        for i in range(3):
            _insert_opportunity(
                db_session, f"page-{i}", topic_tags='["ada-compliance"]'
            )

        response = client.get("/api/v1/opportunities/ada-compliance?per_page=2&page=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["total"] >= 3
        assert data["pages"] >= 2

        response2 = client.get("/api/v1/opportunities/ada-compliance?per_page=2&page=2")
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["results"]) >= 1

    def test_endpoint_no_auth_required(self, client, db_session):
        _insert_opportunity(db_session, "noauth-1", topic_tags='["ada-compliance"]')
        response = client.get("/api/v1/opportunities/ada-compliance")
        assert response.status_code == 200

    def test_municipality_filter(self, client, db_session):
        _insert_opportunity(
            db_session,
            "muni-1",
            topic_tags='["ada-compliance"]',
            description="ADA compliance grants for the city of boston area transit",
        )
        _insert_opportunity(
            db_session,
            "muni-2",
            topic_tags='["ada-compliance"]',
            description="General accessible infrastructure funding",
        )
        response = client.get(
            "/api/v1/opportunities/ada-compliance?municipality=boston"
        )
        assert response.status_code == 200
        data = response.json()
        ids = [r["id"] for r in data["results"]]
        assert "muni-1" in ids
        assert "muni-2" not in ids

    def test_municipality_fallback(self, client, db_session):
        """No match for municipality slug — fail-open returns all ADA grants."""
        _insert_opportunity(
            db_session,
            "fall-1",
            topic_tags='["ada-compliance"]',
            description="general grant for accessibility",
        )
        response = client.get(
            "/api/v1/opportunities/ada-compliance?municipality=nonexistent-city"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_invalid_param_422(self, client, db_session):
        response = client.get("/api/v1/opportunities/ada-compliance?per_page=200")
        assert response.status_code == 422

    def test_endpoint_excludes_non_ada(self, client, db_session):
        _insert_opportunity(db_session, "noada-1", topic_tags='["health"]')
        response = client.get("/api/v1/opportunities/ada-compliance")
        assert response.status_code == 200
        data = response.json()
        # The "health" only grant must not appear
        ids = [r["id"] for r in data["results"]]
        assert "noada-1" not in ids
