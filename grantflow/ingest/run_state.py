"""Orchestrator for state grant portal scrapers."""

from datetime import datetime, timezone

from grantflow.database import init_db, SessionLocal
from grantflow.ingest.run_all import _write_pipeline_run
from grantflow.pipeline.logging import configure_structlog, bind_source_logger
from grantflow.pipeline.monitor import check_zero_records

logger = bind_source_logger("state_pipeline")


def _get_scrapers():
    """Import and instantiate all state scrapers."""
    from grantflow.ingest.state.california import CaliforniaScraper  # noqa: PLC0415
    from grantflow.ingest.state.north_carolina import NorthCarolinaScraper  # noqa: PLC0415
    from grantflow.ingest.state.new_york import NewYorkScraper  # noqa: PLC0415
    from grantflow.ingest.state.illinois import IllinoisScraper  # noqa: PLC0415
    from grantflow.ingest.state.texas import TexasScraper  # noqa: PLC0415
    from grantflow.ingest.state.colorado import ColoradoScraper  # noqa: PLC0415
    from grantflow.ingest.state.florida import FloridaScraper  # noqa: PLC0415

    return [
        CaliforniaScraper(),
        NorthCarolinaScraper(),
        NewYorkScraper(),
        IllinoisScraper(),
        TexasScraper(),
        ColoradoScraper(),
        FloridaScraper(),
    ]


def run_state_ingestion() -> dict:
    """Run all state scrapers. Returns summary dict."""
    started = datetime.now(timezone.utc)
    logger.info("state_ingestion_start", started_at=started.isoformat())
    init_db()

    scrapers = _get_scrapers()
    results = {}

    for i, scraper in enumerate(scrapers, 1):
        logger.info(
            "state_ingestion_step",
            step=i,
            total=len(scrapers),
            source=scraper.source_name,
        )
        source_started = datetime.now(timezone.utc)
        result = scraper.run()
        results[scraper.source_name] = result
        _write_pipeline_run(scraper.source_name, result, source_started)
        logger.info(
            "state_ingestion_step_complete",
            source=scraper.source_name,
            status=result.get("status"),
            records_processed=result.get("records_processed", 0),
        )

    # Zero-record check after all state scrapers complete
    broken = check_zero_records()
    if broken:
        logger.warning("state_scrapers_zero_records", sources=broken)

    # Assign canonical IDs for deduplication
    from grantflow.dedup import assign_canonical_ids  # noqa: PLC0415

    session = SessionLocal()
    try:
        dedup_stats = assign_canonical_ids(session)
        logger.info("canonical_ids_assigned", **dedup_stats)
    finally:
        session.close()

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    summary = {
        "sources": results,
        "elapsed_seconds": round(elapsed, 1),
        "broken_scrapers": broken,
    }
    logger.info("state_ingestion_complete", elapsed_seconds=summary["elapsed_seconds"])
    return summary


def main():
    """CLI entry point for running state ingestion."""
    import os

    configure_structlog(env=os.getenv("GRANTFLOW_ENV", "development"))
    run_state_ingestion()


if __name__ == "__main__":
    main()
