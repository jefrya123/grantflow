"""Test scaffolds for state monitor behaviors (STATE-04 behaviors).

These tests are RED until Plan 03 implements:
  - check_zero_records() in pipeline/monitor.py
  - Per-source stale thresholds (240h for weekly state sources)
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


def test_state_stale_threshold(db_session):
    """State sources with 240h threshold are NOT stale when run was 5 days (120h) ago."""
    from grantflow.pipeline.monitor import check_staleness_with_thresholds  # noqa: PLC0415

    completed_at = (datetime.now(timezone.utc) - timedelta(hours=120)).isoformat()
    _make_pipeline_run(
        "state_california", "success", completed_at, db_session, records_processed=50
    )

    # Per-source thresholds: state sources get 240h window
    per_source_thresholds = {"state_california": 240}
    stale = check_staleness_with_thresholds(db_session, per_source_thresholds)

    # 120h < 240h threshold, so state_california should NOT be stale
    assert "state_california" not in stale
