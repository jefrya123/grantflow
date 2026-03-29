"""Tests for ADA backfill script and matching logic.

Covers:
- Matching logic finds the FTA "All Stations Accessibility Program" grant
- topic_tags updated correctly: NULL → new array, existing array → appended
- Idempotency: running twice does not duplicate the tag
"""

import json
from sqlalchemy import text

from grantflow.pipeline.ada_tagger import _is_ada_match, run_ada_backfill


# ---------------------------------------------------------------------------
# FTA grant matching
# ---------------------------------------------------------------------------


class TestFTAGrantMatching:
    def test_all_stations_accessibility_title_matches(self):
        """The FTA 'All Stations Accessibility Program' title must match."""
        assert _is_ada_match("All Stations Accessibility Program", None, None) is True

    def test_fta_agency_matches(self):
        """Any grant from Federal Transit Administration must match."""
        assert _is_ada_match(None, None, "Federal Transit Administration") is True

    def test_fta_grant_by_title_and_agency(self):
        """Matching by both title and agency (real grant pattern)."""
        assert (
            _is_ada_match(
                "All Stations Accessibility Program",
                None,
                "Federal Transit Administration",
            )
            is True
        )


# ---------------------------------------------------------------------------
# topic_tags update behaviour
# ---------------------------------------------------------------------------


def _insert_row(db_session, row_id, title, topic_tags=None):
    db_session.execute(
        text(
            "INSERT INTO opportunities "
            "(id, title, topic_tags, source, source_id) "
            "VALUES (:id, :title, :tags, 'test', :id)"
        ),
        {"id": row_id, "title": title, "tags": topic_tags},
    )
    db_session.flush()


class TestTopicTagsUpdate:
    def test_null_tags_become_new_array(self, db_session):
        """NULL topic_tags → '["ada-compliance"]'."""
        _insert_row(
            db_session, "bf-null-1", "ADA Compliance Sidewalk Grant", topic_tags=None
        )

        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'bf-null-1'")
        ).fetchone()
        assert json.loads(row[0]) == ["ada-compliance"]

    def test_existing_tags_get_appended(self, db_session):
        """Existing tags preserved; ada-compliance appended."""
        _insert_row(
            db_session,
            "bf-exist-1",
            "Wheelchair Accessible Transit Improvements",
            topic_tags='["transportation", "health"]',
        )

        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'bf-exist-1'")
        ).fetchone()
        tags = json.loads(row[0])
        assert "transportation" in tags
        assert "health" in tags
        assert "ada-compliance" in tags


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_running_twice_does_not_duplicate_tag(self, db_session):
        """ada-compliance must appear exactly once after two backfill runs."""
        _insert_row(db_session, "idem-bf-1", "Curb Cut Accessibility Program")

        run_ada_backfill(db=db_session)
        db_session.flush()
        run_ada_backfill(db=db_session)

        row = db_session.execute(
            text("SELECT topic_tags FROM opportunities WHERE id = 'idem-bf-1'")
        ).fetchone()
        tags = json.loads(row[0])
        assert tags.count("ada-compliance") == 1
