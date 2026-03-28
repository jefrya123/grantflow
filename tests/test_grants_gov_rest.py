"""Tests for Grants.gov dual-source ingest strategy (REST + XML fallback)."""

import json
from unittest.mock import MagicMock, patch

import httpx

from grantflow.ingest.grants_gov import (
    MIN_REST_THRESHOLD,
    _ingest_via_rest,
    ingest_grants_gov,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_session_mock():
    """Return a MagicMock that quacks like a SQLAlchemy session."""
    session = MagicMock()
    session.get.return_value = None  # every record is new (no existing row)
    return session


def _opp_hit(n: int) -> dict:
    """Return a minimal oppHit dict for record #n."""
    return {
        "id": str(1000 + n),
        "title": f"Grant {n}",
        "number": f"NUM-{n}",
        "agencyName": "Test Agency",
        "agencyCode": "TST",
        "openDate": "2026-01-01",
        "closeDate": "2026-06-30",
        "opportunityCategory": "D",
        "awardCeiling": 50000.0,
        "awardFloor": 1000.0,
        "description": f"Description {n}",
        "cfdaList": ["93.123"],
    }


def _mock_response(status_code: int, body: dict | None = None) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = json.dumps(body) if body else ""
    if body is not None:
        resp.json.return_value = body
    else:
        resp.json.side_effect = ValueError("no body")
    return resp


def _search2_body(hits: list[dict], total: int | None = None) -> dict:
    return {
        "data": {
            "oppHits": hits,
            "totalOpportunityCount": total if total is not None else len(hits),
        }
    }


# ─── Test: 5xx → return None ──────────────────────────────────────────────────


def test_rest_returns_none_on_5xx():
    """_ingest_via_rest returns None when the API returns a 5xx status."""
    session = _make_session_mock()
    with patch("httpx.post", return_value=_mock_response(500)):
        result = _ingest_via_rest(session)
    assert result is None, "Expected None on 5xx response"


# ─── Test: below threshold → return None ──────────────────────────────────────


def test_rest_returns_none_below_threshold():
    """_ingest_via_rest returns None when fewer than MIN_REST_THRESHOLD records are returned."""
    # Return 10 records (well below threshold of 100)
    hits = [_opp_hit(i) for i in range(10)]
    body = _search2_body(hits, total=10)

    session = _make_session_mock()
    with patch("httpx.post", return_value=_mock_response(200, body)):
        result = _ingest_via_rest(session)

    assert result is None, (
        f"Expected None when records ({len(hits)}) < MIN_REST_THRESHOLD ({MIN_REST_THRESHOLD})"
    )


# ─── Test: REST success path ──────────────────────────────────────────────────


def test_rest_returns_stats_above_threshold():
    """_ingest_via_rest returns a stats dict when enough records are returned.

    The mock returns exactly MIN_REST_THRESHOLD hits on the first page and
    signals exhaustion via totalOpportunityCount == MIN_REST_THRESHOLD so
    pagination stops after one page.
    """
    hits = [_opp_hit(i) for i in range(MIN_REST_THRESHOLD)]
    # total == page size → (0+1)*25 >= 100 is False, so we need total == hits count
    body = _search2_body(hits, total=MIN_REST_THRESHOLD)

    # First call returns all hits; subsequent calls return empty (pagination guard)
    empty_body = _search2_body([], total=MIN_REST_THRESHOLD)

    session = _make_session_mock()
    with patch(
        "httpx.post",
        side_effect=[
            _mock_response(200, body),
            _mock_response(200, empty_body),
        ],
    ):
        result = _ingest_via_rest(session)

    assert result is not None, "Expected stats dict above threshold"
    assert result["records_processed"] == MIN_REST_THRESHOLD
    assert result["status"] == "success"
    extra = json.loads(result["extra"])
    assert extra["path"] == "rest"


# ─── Test: connection error → return None ─────────────────────────────────────


def test_rest_returns_none_on_connection_error():
    """_ingest_via_rest returns None when httpx raises a network error."""
    session = _make_session_mock()
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = _ingest_via_rest(session)
    assert result is None


# ─── Test: ingest_grants_gov falls back to XML when REST fails ────────────────


def test_grants_gov_uses_xml_when_rest_fails():
    """ingest_grants_gov calls _ingest_via_xml when _ingest_via_rest returns None."""
    xml_stats = {
        "source": "grants_gov",
        "status": "success",
        "records_processed": 500,
        "records_added": 500,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
        "extra": json.dumps({"path": "xml"}),
    }

    with (
        patch(
            "grantflow.ingest.grants_gov._ingest_via_rest", return_value=None
        ) as mock_rest,
        patch(
            "grantflow.ingest.grants_gov._ingest_via_xml", return_value=xml_stats
        ) as mock_xml,
        patch("grantflow.ingest.grants_gov.SessionLocal") as mock_session_local,
        patch("grantflow.ingest.grants_gov.GRANTS_GOV_USE_REST", False),
    ):
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        result = ingest_grants_gov()

    mock_rest.assert_called_once()
    mock_xml.assert_called_once()
    assert result["status"] == "success"
    assert result["records_processed"] == 500
    extra = json.loads(result.get("extra", "{}"))
    assert extra["path"] == "xml"


# ─── Test: REST-only mode error when REST unavailable ─────────────────────────


def test_grants_gov_rest_only_errors_when_rest_unavailable():
    """ingest_grants_gov returns error when REST-only mode set and REST returns None."""
    with (
        patch("grantflow.ingest.grants_gov._ingest_via_rest", return_value=None),
        patch("grantflow.ingest.grants_gov.SessionLocal") as mock_session_local,
        patch("grantflow.ingest.grants_gov.GRANTS_GOV_USE_REST", True),
    ):
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        result = ingest_grants_gov()

    assert result["status"] == "error"
    assert "REST API unavailable" in result["error"]
