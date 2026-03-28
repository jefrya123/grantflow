"""Smoke tests: pipeline imports and initialization."""

from __future__ import annotations



def test_run_all_imports_and_is_callable() -> None:
    """run_all.py imports cleanly and run_all_ingestion is callable."""
    from grantflow.ingest.run_all import run_all_ingestion

    assert callable(run_all_ingestion)


def test_run_state_imports_and_is_callable() -> None:
    """run_state.py imports cleanly and run_state_ingestion is callable."""
    from grantflow.ingest.run_state import run_state_ingestion

    assert callable(run_state_ingestion)


def test_get_scrapers_returns_six_instances() -> None:
    """_get_scrapers() returns exactly 6 state scraper instances."""
    from grantflow.ingest.run_state import _get_scrapers

    scrapers = _get_scrapers()
    assert len(scrapers) == 6


def test_each_scraper_has_required_attributes() -> None:
    """Every state scraper instance has source_name and state_code string attrs."""
    from grantflow.ingest.run_state import _get_scrapers

    scrapers = _get_scrapers()
    for scraper in scrapers:
        assert isinstance(scraper.source_name, str), (
            f"{type(scraper).__name__} missing string source_name"
        )
        assert isinstance(scraper.state_code, str), (
            f"{type(scraper).__name__} missing string state_code"
        )
        assert scraper.source_name, f"{type(scraper).__name__}.source_name is empty"
        assert scraper.state_code, f"{type(scraper).__name__}.state_code is empty"


def test_colorado_normalize_record_returns_expected_keys() -> None:
    """ColoradoScraper.normalize_record() handles a sample record correctly."""
    from grantflow.ingest.state.colorado import ColoradoScraper

    scraper = ColoradoScraper()
    sample = {
        "title": "Test Grant",
        "agency": "CO Dept",
        "deadline": "2026-12-31",
        "url": "https://example.com",
    }
    result = scraper.normalize_record(sample)

    assert result is not None
    assert "id" in result
    assert "source" in result
    assert "title" in result
    assert "agency_name" in result
    assert result["title"] == "Test Grant"
    assert result["source"] == "state_colorado"
    assert result["id"].startswith("state_co_")
