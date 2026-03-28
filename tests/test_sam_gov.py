"""Tests for SAM.gov ingestor."""

import grantflow.ingest.sam_gov as sam_gov_module
from grantflow.ingest.sam_gov import ingest_sam_gov
from grantflow.normalizers import normalize_date


def test_ingest_sam_gov_skips_without_api_key(monkeypatch):
    """When SAM_GOV_API_KEY is not set, ingest_sam_gov() returns status='skipped'."""
    monkeypatch.setattr(sam_gov_module, "SAM_GOV_API_KEY", "")
    result = ingest_sam_gov()
    assert result["status"] == "skipped", (
        f"Expected 'skipped', got '{result['status']}'"
    )
    # Should not have processed any records
    assert result["records_processed"] == 0
    assert result["records_added"] == 0
    assert result["records_updated"] == 0


# ---------------------------------------------------------------------------
# normalize_date tests (migrated from _parse_sam_date)
# ---------------------------------------------------------------------------


def test_normalize_date_iso_with_offset():
    """normalize_date handles ISO 8601 with timezone offset."""
    result = normalize_date("2024-03-15T00:00:00-04:00")
    assert result == "2024-03-15"


def test_normalize_date_plain_date():
    """normalize_date handles plain YYYY-MM-DD."""
    result = normalize_date("2024-06-01")
    assert result == "2024-06-01"


def test_normalize_date_slash_format():
    """normalize_date handles MM/DD/YYYY format."""
    result = normalize_date("12/31/2024")
    assert result == "2024-12-31"


def test_normalize_date_none():
    """normalize_date returns None for None input."""
    assert normalize_date(None) is None


def test_normalize_date_empty():
    """normalize_date returns None for empty string."""
    assert normalize_date("") is None


# ---------------------------------------------------------------------------
# Normalization wire tests (verify sam_gov.py uses shared normalizers)
# ---------------------------------------------------------------------------


def test_sam_gov_normalizes_eligibility():
    """sam_gov.py imports and uses normalize_eligibility_codes from normalizers."""
    source = open(sam_gov_module.__file__).read()
    assert "normalize_eligibility_codes" in source, (
        "sam_gov.py must call normalize_eligibility_codes() from grantflow.normalizers"
    )


def test_sam_gov_normalizes_agency():
    """sam_gov.py imports and uses normalize_agency_name from normalizers."""
    source = open(sam_gov_module.__file__).read()
    assert "normalize_agency_name" in source, (
        "sam_gov.py must call normalize_agency_name() from grantflow.normalizers"
    )


def test_sam_gov_uses_normalize_date():
    """sam_gov.py uses normalize_date (not _parse_sam_date) for date fields."""
    source = open(sam_gov_module.__file__).read()
    assert "_parse_sam_date" not in source, (
        "sam_gov.py must not reference _parse_sam_date; use normalize_date() instead"
    )
    assert "normalize_date" in source, (
        "sam_gov.py must use normalize_date() from grantflow.normalizers"
    )
