"""Tests for state monitor behaviors: zero-record detection and per-source stale thresholds.

Covers STATE-04 requirements:
  - check_zero_records() in pipeline/monitor.py
  - Per-source stale thresholds (240h for weekly state sources, 48h for federal)
"""

import pytest
from datetime import datetime, timezone, timedelta

from grantflow.models import PipelineRun


def _make_pipeline_run(
    source: str,
    status: str,
    completed_at: str,
    session,
    records_processed: int = 0,
) -> PipelineRun:
    run = PipelineRun(
        source=source,
        status=status,
        started_at=completed_at,
        completed_at=completed_at,
        records_processed=records_processed,
    )
    session.add(run)
    session.flush()
    return run


def test_zero_records_detection(db_session):
    """check_zero_records() returns source name when last successful run has records_processed=0."""
    from grantflow.pipeline.monitor import check_zero_records  # noqa: PLC0415

    completed_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _make_pipeline_run(
        "state_california", "success", completed_at, db_session, records_processed=0
    )

    result = check_zero_records(db_session)
    assert "state_california" in result


def test_zero_records_ignores_federal(db_session):
    """check_zero_records() does NOT check federal sources (grants_gov, usaspending, etc.)."""
    from grantflow.pipeline.monitor import check_zero_records  # noqa: PLC0415

    completed_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _make_pipeline_run(
        "grants_gov", "success", completed_at, db_session, records_processed=0
    )

    result = check_zero_records(db_session)
    assert "grants_gov" not in result


def test_zero_records_ignores_error_runs(db_session):
    """A PipelineRun with status='error' and records_processed=0 is NOT flagged."""
    from grantflow.pipeline.monitor import check_zero_records  # noqa: PLC0415

    completed_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    _make_pipeline_run(
        "state_new_york", "error", completed_at, db_session, records_processed=0
    )

    result = check_zero_records(db_session)
    assert "state_new_york" not in result


def test_state_stale_threshold(db_session):
    """State source completed 5 days ago (120h) is NOT stale with 240h threshold."""
    from grantflow.pipeline.monitor import check_staleness  # noqa: PLC0415

    # 120h ago — within 240h state threshold but beyond 48h federal threshold
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=120)).isoformat()
    _make_pipeline_run(
        "state_california", "success", completed_at, db_session, records_processed=50
    )

    stale = check_staleness(db_session)
    assert "state_california" not in stale


def test_federal_stale_threshold_unchanged(db_session):
    """Federal sources still use 48h threshold after the per-source refactor."""
    from grantflow.pipeline.monitor import check_staleness  # noqa: PLC0415

    # 50h ago — beyond 48h federal threshold
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=50)).isoformat()
    _make_pipeline_run(
        "grants_gov", "success", completed_at, db_session, records_processed=100
    )

    stale = check_staleness(db_session)
    assert "grants_gov" in stale
