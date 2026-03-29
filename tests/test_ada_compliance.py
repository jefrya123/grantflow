"""Unit tests for ADA keyword matching and backfill logic."""
import json
import pytest
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
        assert _is_ada_match("Americans with Disabilities Act Grant", None, None) is True

    def test_ada_compliance_in_title(self):
        assert _is_ada_match("ADA Compliance Infrastructure Program", None, None) is True

    def test_federal_transit_administration_in_agency(self):
        assert _is_ada_match(None, None, "Federal Transit Administration") is True

    def test_paratransit_in_description(self):
        assert _is_ada_match(None, "This grant funds paratransit services for riders", None) is True

    def test_all_stations_accessibility_in_title(self):
        assert _is_ada_match("All Stations Accessibility Program", None, None) is True

    def test_section_504_in_description(self):
        assert _is_ada_match(None, "Compliance with Section 504 of the Rehabilitation Act", None) is True

    def test_wheelchair_in_title(self):
        assert _is_ada_match("Wheelchair Accessible Station Improvements", None, None) is True

    def test_curb_cut_in_description(self):
        assert _is_ada_match(None, "Funding for curb cut installation at intersections", None) is True


# ---------------------------------------------------------------------------
# Keyword matching — False cases (false positive prevention)
# ---------------------------------------------------------------------------

class TestKeywordMatchingFalse:
    def test_adaptation_program_bare_ada_substring_in_title(self):
        """'ADAPTATION' contains 'ada' as substring — must NOT match."""
        assert _is_ada_match("ADAPTATION program for rural communities", None, None) is False

    def test_adams_county_in_title(self):
        """'Adams' contains 'ada' as substring — must NOT match."""
        assert _is_ada_match("Adams County Rural Development Grant", None, None) is False

    def test_nadac_pricing_in_title(self):
        """'NADAC' contains 'ada' as substring — must NOT match."""
        assert _is_ada_match("NADAC Pricing Initiative", None, None) is False

    def test_academic_in_description(self):
        """'academic' contains 'ada' as substring — must NOT match."""
        assert _is_ada_match(None, "Support for academic research programs", None) is False

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
    def _insert_row(self, db_session, row_id, title, description=None, agency_name=None, topic_tags=None, source="test"):
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
        self._insert_row(db_session, "back-2", "Rural Roads Program", agency_name="Federal Transit Administration")
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
        self._insert_row(db_session, "idem-1", "Wheelchair Accessible Transit Improvements")

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
