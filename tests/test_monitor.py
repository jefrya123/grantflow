"""Tests for pipeline staleness monitor."""

import pytest
from datetime import datetime, timezone, timedelta

from grantflow.models import PipelineRun
from grantflow.pipeline.monitor import get_freshness_report, check_staleness, STALE_THRESHOLD_HOURS


def _make_pipeline_run(source: str, status: str, completed_at: str, session) -> PipelineRun:
    run = PipelineRun(
        source=source,
        status=status,
        started_at=completed_at,
        completed_at=completed_at,
    )
    session.add(run)
    session.flush()
    return run


def test_freshness_report_never_run(db_session):
    """Empty DB → all known sources show 'never_run'."""
    report = get_freshness_report(db_session)

    assert set(report.keys()) == {"grants_gov", "usaspending", "sbir", "sam_gov"}
    for source, info in report.items():
        assert info["status"] == "never_run", f"{source} should be never_run"
        assert info["last_success"] is None
        assert info["hours_since"] is None


def test_freshness_report_ok(db_session):
    """A recent successful PipelineRun → source shows 'ok'."""
    recent = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    _make_pipeline_run("grants_gov", "success", recent, db_session)

    report = get_freshness_report(db_session)

    assert report["grants_gov"]["status"] == "ok"
    assert report["grants_gov"]["last_success"] == recent
    assert report["grants_gov"]["hours_since"] is not None
    assert report["grants_gov"]["hours_since"] < STALE_THRESHOLD_HOURS


def test_freshness_report_stale(db_session):
    """A PipelineRun completed 50h ago → source shows 'stale'."""
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
    _make_pipeline_run("usaspending", "success", old_ts, db_session)

    report = get_freshness_report(db_session)

    assert report["usaspending"]["status"] == "stale"
    assert report["usaspending"]["hours_since"] > STALE_THRESHOLD_HOURS


def test_freshness_report_ignores_failed_runs(db_session):
    """A failed PipelineRun does NOT count as a success → still 'never_run'."""
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _make_pipeline_run("sbir", "error", recent, db_session)

    report = get_freshness_report(db_session)

    assert report["sbir"]["status"] == "never_run"


def test_check_staleness_returns_stale_list(db_session):
    """check_staleness() returns list of stale source names."""
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
    _make_pipeline_run("sam_gov", "success", old_ts, db_session)

    stale = check_staleness(db_session)

    assert "sam_gov" in stale
    assert len(stale) == 1


def test_check_staleness_empty_when_all_fresh(db_session):
    """check_staleness() returns empty list when all sources with runs are fresh."""
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _make_pipeline_run("grants_gov", "success", recent, db_session)

    stale = check_staleness(db_session)

    # grants_gov is fresh; others are never_run (not stale)
    assert stale == []
