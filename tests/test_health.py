from datetime import datetime, timedelta, timezone

from grantflow.models import IngestionLog, Opportunity
from grantflow.pipeline.monitor import get_freshness_report


def test_health_empty_db(client):
    """Health endpoint returns 200 with ok status when no ingestion logs exist."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["sources"] == {}
    assert "checked_at" in data


def test_health_recent_ingestion(client, db_session):
    """Status is ok when last ingestion was less than 48 hours ago."""
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    log = IngestionLog(
        source="grants_gov",
        started_at=recent.isoformat(),
        completed_at=recent.isoformat(),
        status="success",
        records_added=100,
        records_processed=100,
    )
    db_session.add(log)
    db_session.commit()

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "grants_gov" in data["sources"]
    assert data["sources"]["grants_gov"]["last_status"] == "success"
    assert data["sources"]["grants_gov"]["stale"] is False


def test_health_stale_ingestion(client, db_session):
    """Status is stale when last successful ingestion was more than 48 hours ago."""
    old = datetime.now(timezone.utc) - timedelta(hours=72)
    log = IngestionLog(
        source="sbir",
        started_at=old.isoformat(),
        completed_at=old.isoformat(),
        status="success",
        records_added=50,
        records_processed=50,
    )
    db_session.add(log)
    db_session.commit()

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stale"
    assert data["sources"]["sbir"]["stale"] is True


def test_health_error_log_does_not_crash(client, db_session):
    """Health endpoint returns 200 even when latest log entry has status=error."""
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    log = IngestionLog(
        source="usaspending",
        started_at=recent.isoformat(),
        completed_at=recent.isoformat(),
        status="error",
        error="Connection refused",
        records_added=0,
        records_processed=0,
    )
    db_session.add(log)
    db_session.commit()

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "usaspending" in data["sources"]


def test_source_freshness_falls_back_to_ingestion_log(db_session):
    """source_freshness uses IngestionLog when no PipelineRun exists for federal sources."""
    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    log = IngestionLog(
        source="grants_gov",
        started_at=recent.isoformat(),
        completed_at=recent.isoformat(),
        status="success",
        records_added=81000,
        records_processed=81000,
    )
    db_session.add(log)
    db_session.commit()

    report = get_freshness_report(db_session)

    assert report["grants_gov"]["status"] == "ok"
    assert report["grants_gov"]["last_success"] is not None
    assert report["grants_gov"]["hours_since"] is not None


def test_health_record_counts(client, db_session):
    """record_count reflects actual Opportunity row count per source."""
    # Use a unique source to avoid contamination from other tests that commit
    # grants_gov records into the session-scoped test database.
    source = "test_record_count_source"
    for i in range(3):
        opp = Opportunity(
            id=f"{source}_{i}",
            source=source,
            source_id=f"test_{i}",
            title=f"Test Opportunity {i}",
        )
        db_session.add(opp)
    db_session.commit()

    log = IngestionLog(
        source=source,
        started_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
        status="success",
        records_added=3,
        records_processed=3,
    )
    db_session.add(log)
    db_session.commit()

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["sources"][source]["record_count"] == 3
