"""Tests for CFDA normalization and opportunity-to-award linking."""

import pytest

from grantflow.models import Opportunity, Award
from grantflow.pipeline.cfda_link import normalize_cfda, link_opportunities_to_awards


# ---------------------------------------------------------------------------
# normalize_cfda unit tests (no DB required)
# ---------------------------------------------------------------------------

def test_normalize_cfda_standard():
    """Already-canonical input passes through unchanged."""
    assert normalize_cfda("84.007") == "84.007"


def test_normalize_cfda_hyphen():
    """Hyphen separator is converted to dot."""
    assert normalize_cfda("84-007") == "84.007"


def test_normalize_cfda_leading_zero_suffix():
    """Single-digit suffix is zero-padded to 3 digits."""
    assert normalize_cfda("84.7") == "84.007"


def test_normalize_cfda_padded_prefix():
    """Leading zero in prefix is stripped."""
    assert normalize_cfda("084.007") == "84.007"


def test_normalize_cfda_empty():
    """None and empty string both return empty string."""
    assert normalize_cfda(None) == ""
    assert normalize_cfda("") == ""


def test_normalize_cfda_space_separator():
    """Space separator is converted to dot."""
    assert normalize_cfda("84 007") == "84.007"


def test_normalize_cfda_whitespace_stripped():
    """Leading/trailing whitespace is stripped."""
    assert normalize_cfda("  84.007  ") == "84.007"


def test_normalize_cfda_two_digit_suffix():
    """Two-digit suffix is zero-padded to 3 digits."""
    assert normalize_cfda("84.07") == "84.007"


# ---------------------------------------------------------------------------
# link_opportunities_to_awards integration tests (requires DB session)
# ---------------------------------------------------------------------------

def _make_opportunity(session, opp_id: str, cfda: str | None) -> Opportunity:
    opp = Opportunity(
        id=opp_id,
        source="test",
        source_id=opp_id,
        title=f"Test Opportunity {opp_id}",
        cfda_numbers=cfda,
    )
    session.add(opp)
    session.flush()
    return opp


def _make_award(session, award_id: str, cfda: str | None) -> Award:
    award = Award(
        id=award_id,
        source="test",
        award_id=award_id,
        cfda_numbers=cfda,
    )
    session.add(award)
    session.flush()
    return award


def test_link_opportunities_empty_db(db_session):
    """link_opportunities_to_awards() runs without error on empty DB."""
    stats = link_opportunities_to_awards(db_session)
    assert stats["opportunities_processed"] == 0
    assert stats["cfda_normalized"] == 0
    assert stats["award_links_found"] == 0


def test_link_normalizes_cfda_in_place(db_session):
    """Opportunities with non-canonical CFDA are updated in place."""
    _make_opportunity(db_session, "opp-1", "84-007")  # hyphen → should normalize

    stats = link_opportunities_to_awards(db_session)

    assert stats["opportunities_processed"] == 1
    assert stats["cfda_normalized"] == 1

    # Verify the value was actually updated in the session
    opp = db_session.query(Opportunity).filter_by(id="opp-1").first()
    assert opp.cfda_numbers == "84.007"


def test_link_finds_matching_awards(db_session):
    """Matching CFDA numbers between opportunity and award are counted."""
    _make_opportunity(db_session, "opp-2", "84.007")
    _make_award(db_session, "award-1", "84.007")

    stats = link_opportunities_to_awards(db_session)

    assert stats["opportunities_processed"] == 1
    assert stats["award_links_found"] >= 1


def test_link_skips_null_cfda(db_session):
    """Opportunities with null or empty cfda_numbers are skipped."""
    _make_opportunity(db_session, "opp-null", None)
    _make_opportunity(db_session, "opp-empty", "")

    stats = link_opportunities_to_awards(db_session)

    assert stats["opportunities_processed"] == 0
