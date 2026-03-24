"""Tests for analytics middleware — api_events recording."""
import pytest
from fastapi.testclient import TestClient

from grantflow.models import ApiEvent
from grantflow.database import SessionLocal


def test_event_recorded(client: TestClient):
    """After an API request, an api_events row exists with correct path and status_code."""
    # Count before the request using the same SessionLocal the middleware writes to
    pre_session = SessionLocal()
    try:
        count_before = pre_session.query(ApiEvent).filter(
            ApiEvent.path == "/api/v1/opportunities/search"
        ).count()
    finally:
        pre_session.close()

    resp = client.get("/api/v1/opportunities/search")
    assert resp.status_code in (200, 401, 422)  # any non-5xx acceptable

    # Background tasks run synchronously in TestClient, so the event should be committed.
    post_session = SessionLocal()
    try:
        events = post_session.query(ApiEvent).filter(
            ApiEvent.path == "/api/v1/opportunities/search"
        ).all()
        count_after = len(events)
        assert count_after > count_before, "Expected a new api_events row for the request"
        event = events[-1]
        assert event.path == "/api/v1/opportunities/search"
        assert event.method == "GET"
        assert event.status_code in (200, 401, 422)
        assert event.duration_ms >= 0
    finally:
        post_session.close()


def test_analytics_skips_static(client: TestClient):
    """Static file requests are not recorded in api_events."""
    pre_session = SessionLocal()
    try:
        count_before = pre_session.query(ApiEvent).count()
    finally:
        pre_session.close()

    client.get("/static/style.css")

    post_session = SessionLocal()
    try:
        count_after = post_session.query(ApiEvent).count()
    finally:
        post_session.close()

    assert count_after == count_before, "Static requests should not be recorded"
