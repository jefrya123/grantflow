"""Tests for weekly email digest (saved search alerts)."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from grantflow.models import SavedSearch, Opportunity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_opportunity(db, title, post_date, close_date=None, source_url=None, agency_name=None):
    slug = title[:8].replace(' ', '-').lower()
    opp = Opportunity(
        id=f"test-{slug}-{post_date}",
        source_id=f"src-{slug}-{post_date}",
        title=title,
        agency_name=agency_name or "Test Agency",
        post_date=post_date,
        close_date=close_date,
        source_url=source_url or "https://example.gov/grant",
        source="test",
    )
    db.add(opp)
    db.flush()
    return opp


def _make_search(db, name="Test Search", query=None, agency_code=None, alert_email="user@example.com", is_active=True):
    s = SavedSearch(
        api_key_id=1,
        name=name,
        query=query,
        agency_code=agency_code,
        alert_email=alert_email,
        is_active=is_active,
    )
    db.add(s)
    db.flush()
    return s


# ---------------------------------------------------------------------------
# match_saved_search
# ---------------------------------------------------------------------------

def test_match_saved_search_returns_opps_since_date(db_session):
    from grantflow.digest import match_saved_search

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    old_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    _make_opportunity(db_session, "New Grant", post_date=today)
    _make_opportunity(db_session, "Yesterday Grant", post_date=yesterday)
    _make_opportunity(db_session, "Old Grant", post_date=old_date)

    search = _make_search(db_session)

    # Since two days ago — should return today and yesterday, not old
    since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")
    results = match_saved_search(db_session, search, since)

    titles = {o.title for o in results}
    assert "New Grant" in titles
    assert "Yesterday Grant" in titles
    assert "Old Grant" not in titles


def test_match_saved_search_respects_agency_filter(db_session):
    from grantflow.digest import match_saved_search

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "HHS Grant", post_date=today, agency_name=None)
    opp2 = Opportunity(
        id="test-epa-opp",
        source_id="src-epa-opp",
        title="EPA Grant",
        agency_name="EPA",
        agency_code="EPA",
        post_date=today,
        source="test",
    )
    db_session.add(opp2)
    db_session.flush()

    search = _make_search(db_session, agency_code="EPA")
    since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    results = match_saved_search(db_session, search, since)

    assert all("EPA" in (o.agency_code or "") for o in results)


def test_match_saved_search_returns_empty_when_no_matches(db_session):
    from grantflow.digest import match_saved_search

    old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "Old Grant", post_date=old_date)

    search = _make_search(db_session)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    results = match_saved_search(db_session, search, since)

    assert results == []


# ---------------------------------------------------------------------------
# render_digest
# ---------------------------------------------------------------------------

def test_render_digest_contains_title_and_link(db_session):
    from grantflow.digest import render_digest

    search = _make_search(db_session, name="My Search")
    opp = _make_opportunity(
        db_session,
        "Clean Water Grant",
        post_date="2026-03-01",
        close_date="2026-06-01",
        source_url="https://example.gov/clean-water",
    )

    body = render_digest(search, [opp])

    assert "Clean Water Grant" in body
    assert "https://example.gov/clean-water" in body


def test_render_digest_contains_deadline_bold(db_session):
    from grantflow.digest import render_digest

    search = _make_search(db_session)
    opp = _make_opportunity(
        db_session,
        "Grant With Deadline",
        post_date="2026-03-01",
        close_date="2026-07-15",
    )

    body = render_digest(search, [opp])

    # Deadline should be bolded with ** markers
    assert "**2026-07-15**" in body


def test_render_digest_contains_unsubscribe_note(db_session):
    from grantflow.digest import render_digest

    search = _make_search(db_session)
    opp = _make_opportunity(db_session, "Some Grant", post_date="2026-03-01")

    body = render_digest(search, [opp])

    assert "unsubscribe" in body.lower()


def test_render_digest_multiple_opps(db_session):
    from grantflow.digest import render_digest

    search = _make_search(db_session)
    opps = [
        _make_opportunity(db_session, f"Grant {i}", post_date="2026-03-01")
        for i in range(3)
    ]

    body = render_digest(search, opps)

    for i in range(3):
        assert f"Grant {i}" in body


# ---------------------------------------------------------------------------
# send_weekly_digests
# ---------------------------------------------------------------------------

def test_send_weekly_digests_skips_inactive_searches(db_session):
    from grantflow.digest import send_weekly_digests

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "Active Grant", post_date=today)
    _make_search(db_session, name="Inactive Search", is_active=False)

    with patch("grantflow.digest.send_digest_email") as mock_send:
        send_weekly_digests(db_session)
        mock_send.assert_not_called()


def test_send_weekly_digests_updates_last_alerted_at(db_session):
    from grantflow.digest import send_weekly_digests

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "New Grant", post_date=today)
    search = _make_search(db_session, name="Active Search")

    assert search.last_alerted_at is None

    with patch("grantflow.digest.send_digest_email"):
        send_weekly_digests(db_session)

    db_session.refresh(search)
    assert search.last_alerted_at is not None


def test_send_weekly_digests_no_smtp_when_zero_matches(db_session):
    from grantflow.digest import send_weekly_digests

    old_date = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "Old Grant", post_date=old_date)
    _make_search(db_session, name="Active Search No Match")

    with patch("grantflow.digest.send_digest_email") as mock_send:
        send_weekly_digests(db_session)
        mock_send.assert_not_called()


def test_send_weekly_digests_sends_one_email_per_matching_search(db_session):
    from grantflow.digest import send_weekly_digests

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _make_opportunity(db_session, "New Grant", post_date=today)
    _make_search(db_session, name="Search A", alert_email="a@example.com")
    _make_search(db_session, name="Search B", alert_email="b@example.com")

    with patch("grantflow.digest.send_digest_email") as mock_send:
        send_weekly_digests(db_session)
        assert mock_send.call_count == 2
        emails_called = {call.args[0] for call in mock_send.call_args_list}
        assert emails_called == {"a@example.com", "b@example.com"}
