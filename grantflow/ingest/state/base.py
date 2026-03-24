"""Abstract base class for state grant portal scrapers."""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from grantflow.database import SessionLocal
from grantflow.models import Opportunity
from grantflow.pipeline.logging import bind_source_logger

# Batch size for DB commits — overridable via config
try:
    from grantflow.config import STATE_SCRAPER_BATCH_SIZE
except ImportError:
    STATE_SCRAPER_BATCH_SIZE = 100


class BaseStateScraper(abc.ABC):
    """Abstract base class that all state grant portal scrapers inherit from.

    Subclasses must define:
        source_name: str — e.g. "state_california"
        state_code: str  — e.g. "ca"

    And implement:
        fetch_records() -> list[dict]
        normalize_record(raw: dict) -> dict | None
    """

    source_name: str
    state_code: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Validate class attributes exist on concrete (non-abstract) subclasses
        if not getattr(cls, "__abstractmethods__", None):
            for attr in ("source_name", "state_code"):
                if not hasattr(cls, attr):
                    raise TypeError(
                        f"{cls.__name__} must define class attribute '{attr}'"
                    )

    @abc.abstractmethod
    def fetch_records(self) -> list[dict]:
        """Fetch raw records from the state portal. Returns a list of raw dicts."""

    @abc.abstractmethod
    def normalize_record(self, raw: dict) -> dict | None:
        """Map a raw portal record to an Opportunity field dict.

        Returns None to skip the record (increments records_failed counter).
        """

    def make_opportunity_id(self, source_id: str) -> str:
        """Generate a collision-safe opportunity ID using the state prefix."""
        return f"state_{self.state_code}_{source_id}"

    def run(self, session: Session | None = None) -> dict:
        """Fetch, normalize, and upsert all records. Returns a stats dict.

        Matches the ingestor contract shape from grantflow/ingest/run_all.py:
            {source, status, records_processed, records_added, records_updated,
             records_failed, error}
        """
        log = bind_source_logger(self.source_name)

        stats: dict = {
            "source": self.source_name,
            "status": "error",
            "records_processed": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_failed": 0,
            "error": None,
        }

        # Fetch raw records
        try:
            raw_records = self.fetch_records()
        except Exception as exc:
            log.error("fetch_records_failed", error=str(exc))
            stats["error"] = str(exc)
            return stats

        log.info("fetch_complete", count=len(raw_records))

        # Determine session ownership
        own_session = session is None
        if own_session:
            session = SessionLocal()

        try:
            batch_count = 0

            for raw in raw_records:
                stats["records_processed"] += 1

                try:
                    normalized = self.normalize_record(raw)
                except Exception as exc:
                    log.warning("normalize_record_error", error=str(exc))
                    stats["records_failed"] += 1
                    continue

                if normalized is None:
                    stats["records_failed"] += 1
                    continue

                # Upsert into Opportunity table (merge by id)
                opp_id = normalized.get("id")
                if not opp_id:
                    log.warning("normalized_record_missing_id", raw=str(raw)[:200])
                    stats["records_failed"] += 1
                    continue

                now_utc = datetime.now(timezone.utc).isoformat()
                normalized["updated_at"] = now_utc

                existing = session.get(Opportunity, opp_id)
                if existing is None:
                    # Insert new record
                    if "created_at" not in normalized:
                        normalized["created_at"] = now_utc
                    opp = Opportunity(**normalized)
                    session.add(opp)
                    stats["records_added"] += 1
                else:
                    # Update existing record
                    for key, value in normalized.items():
                        if key != "id":
                            setattr(existing, key, value)
                    stats["records_updated"] += 1

                batch_count += 1

                if batch_count >= STATE_SCRAPER_BATCH_SIZE:
                    session.commit()
                    batch_count = 0
                    log.debug("batch_committed", size=STATE_SCRAPER_BATCH_SIZE)

            # Commit remaining records
            if batch_count > 0:
                session.commit()

            stats["status"] = "success"
            log.info(
                "scrape_complete",
                records_processed=stats["records_processed"],
                records_added=stats["records_added"],
                records_updated=stats["records_updated"],
                records_failed=stats["records_failed"],
            )

        except Exception as exc:
            log.error("run_failed", error=str(exc))
            stats["error"] = str(exc)
            if own_session:
                session.rollback()

        finally:
            if own_session:
                session.close()

        return stats
