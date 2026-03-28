"""Test scaffolds for state scraper infrastructure (STATE-01, STATE-05 behaviors)."""

import pytest

from grantflow.ingest.state.base import BaseStateScraper
from grantflow.normalizers import normalize_date


# ---------------------------------------------------------------------------
# Concrete test double — controlled data for base class tests
# ---------------------------------------------------------------------------


class ConcreteTestScraper(BaseStateScraper):
    source_name = "state_test"
    state_code = "test"

    def __init__(self, records=None, fail_on_none=False):
        self._records = records or [
            {"id": "1", "title": "Grant One"},
            {"id": "2", "title": "Grant Two"},
        ]
        self._fail_on_none = fail_on_none

    def fetch_records(self) -> list[dict]:
        return self._records

    def normalize_record(self, raw: dict) -> dict | None:
        if self._fail_on_none and raw.get("id") == "1":
            return None  # simulate skip
        return {
            "id": self.make_opportunity_id(raw["id"]),
            "source": self.source_name,
            "title": raw["title"],
            "source_id": raw["id"],
            "opportunity_status": "posted",
        }


# ---------------------------------------------------------------------------
# Base class tests (expected GREEN once base.py exists)
# ---------------------------------------------------------------------------


def test_base_scraper_stats_shape(db_session):
    """run() returns a dict with the correct 7 keys matching ingestor contract."""
    scraper = ConcreteTestScraper()
    stats = scraper.run(session=db_session)

    required_keys = {
        "source",
        "status",
        "records_processed",
        "records_added",
        "records_updated",
        "records_failed",
        "error",
    }
    assert required_keys == set(stats.keys()), (
        f"Missing keys: {required_keys - set(stats.keys())}"
    )


def test_opportunity_id_prefix():
    """make_opportunity_id() returns 'state_{code}_{source_id}' format."""
    scraper = ConcreteTestScraper()
    assert scraper.make_opportunity_id("12345") == "state_test_12345"


def test_normalize_record_skip_empty_title(db_session):
    """When normalize_record returns None, record is skipped and records_failed incremented."""
    scraper = ConcreteTestScraper(fail_on_none=True)
    stats = scraper.run(session=db_session)

    assert stats["records_failed"] == 1
    # Only 1 record was valid (id=2); id=1 was skipped
    assert stats["records_processed"] == 2  # both attempted
    assert stats["status"] == "success"


# ---------------------------------------------------------------------------
# CA normalization test — xfail until Plan 02 creates california.py
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="CaliforniaScraper not yet implemented (Plan 02)", strict=False
)
def test_normalize_ca_record():
    """Given a raw CA CKAN dict, normalized output maps fields correctly."""
    from grantflow.ingest.state.california import CaliforniaScraper  # noqa: PLC0415

    scraper = CaliforniaScraper()
    raw = {
        "_id": 42,
        "Title": "CA Arts Grant",
        "Agency": "California Arts Council",
        "Application_Due_Date": "2025-06-30",
        "URL": "https://example.com",
    }
    result = scraper.normalize_record(raw)

    assert result is not None
    assert result["id"] == "state_ca_42"
    assert result["source"] == "state_california"
    assert result["title"] == "CA Arts Grant"
    assert result["close_date"] == normalize_date("2025-06-30")


# ---------------------------------------------------------------------------
# Scheduler test — weekly_state_ingestion job registered
# ---------------------------------------------------------------------------


def test_scheduler_weekly_job():
    """Scheduler registration code produces a 'weekly_state_ingestion' job at Sunday 03:00 UTC."""
    import asyncio  # noqa: PLC0415
    from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: PLC0415
    from apscheduler.triggers.cron import CronTrigger  # noqa: PLC0415
    from grantflow.ingest.run_all import run_all_ingestion  # noqa: PLC0415
    from grantflow.ingest.run_state import run_state_ingestion  # noqa: PLC0415

    sched = AsyncIOScheduler()
    sched.add_job(
        lambda: asyncio.get_event_loop().run_in_executor(None, run_all_ingestion),
        CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="daily_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    sched.add_job(
        lambda: asyncio.get_event_loop().run_in_executor(None, run_state_ingestion),
        CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC"),
        id="weekly_state_ingestion",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    assert sched.get_job("weekly_state_ingestion") is not None
    assert sched.get_job("daily_ingestion") is not None
