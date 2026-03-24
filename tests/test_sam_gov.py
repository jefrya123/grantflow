"""Tests for SAM.gov ingestor."""

import grantflow.ingest.sam_gov as sam_gov_module
from grantflow.ingest.sam_gov import ingest_sam_gov, _parse_sam_date


def test_ingest_sam_gov_skips_without_api_key(monkeypatch):
    """When SAM_GOV_API_KEY is not set, ingest_sam_gov() returns status='skipped'."""
    monkeypatch.setattr(sam_gov_module, "SAM_GOV_API_KEY", "")
    result = ingest_sam_gov()
    assert result["status"] == "skipped", f"Expected 'skipped', got '{result['status']}'"
    # Should not have processed any records
    assert result["records_processed"] == 0
    assert result["records_added"] == 0
    assert result["records_updated"] == 0


def test_parse_sam_date_iso_with_offset():
    """_parse_sam_date handles ISO 8601 with timezone offset."""
    result = _parse_sam_date("2024-03-15T00:00:00-04:00")
    assert result == "2024-03-15"


def test_parse_sam_date_plain_date():
    """_parse_sam_date handles plain YYYY-MM-DD."""
    result = _parse_sam_date("2024-06-01")
    assert result == "2024-06-01"


def test_parse_sam_date_slash_format():
    """_parse_sam_date handles MM/DD/YYYY format."""
    result = _parse_sam_date("12/31/2024")
    assert result == "2024-12-31"


def test_parse_sam_date_none():
    """_parse_sam_date returns None for None input."""
    assert _parse_sam_date(None) is None


def test_parse_sam_date_empty():
    """_parse_sam_date returns None for empty string."""
    assert _parse_sam_date("") is None
