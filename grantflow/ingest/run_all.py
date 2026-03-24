"""Orchestrator that runs all data ingestion pipelines."""

import json
import logging  # noqa: F401 — kept for any stdlib callers
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from grantflow.database import init_db, engine, SessionLocal
from grantflow.ingest.grants_gov import ingest_grants_gov
from grantflow.ingest.usaspending import ingest_usaspending
from grantflow.ingest.sbir import ingest_sbir
from grantflow.ingest.sam_gov import ingest_sam_gov
from grantflow.models import PipelineRun
from grantflow.pipeline.logging import configure_structlog, bind_source_logger

logger = bind_source_logger("pipeline")



def _write_pipeline_run(source_name: str, result: dict, source_started: datetime) -> None:
    """Write a PipelineRun row for a completed source ingest."""
    try:
        with SessionLocal() as session:
            run = PipelineRun(
                source=source_name,
                run_type="full",
                status=result.get("status", "error"),
                started_at=source_started.isoformat(),
                completed_at=datetime.now(timezone.utc).isoformat(),
                records_processed=result.get("records_processed", 0),
                records_added=result.get("records_added", 0),
                records_updated=result.get("records_updated", 0),
                records_failed=result.get("records_failed", 0),
                error_message=result.get("error"),
                extra=json.dumps(result.get("extra", {})),
            )
            session.add(run)
            session.commit()
    except Exception as exc:
        logger.error("pipeline_run_write_failed", source=source_name, error=str(exc))


def run_all_ingestion() -> dict:
    """Run all ingestion pipelines in sequence. Returns summary stats."""
    started = datetime.now(timezone.utc)
    logger.info("ingestion_run_start", started_at=started.isoformat())

    # 1. Initialize database
    init_db()

    results = {}

    # 2. Grants.gov
    logger.info("ingestion_step", step=1, total=4, source="grants_gov")
    source_started = datetime.now(timezone.utc)
    results["grants_gov"] = ingest_grants_gov()
    _write_pipeline_run("grants_gov", results["grants_gov"], source_started)
    logger.info(
        "ingestion_step_complete",
        source="grants_gov",
        status=results["grants_gov"].get("status"),
        records_processed=results["grants_gov"].get("records_processed", 0),
        records_added=results["grants_gov"].get("records_added", 0),
        records_updated=results["grants_gov"].get("records_updated", 0),
        records_failed=results["grants_gov"].get("records_failed", 0),
    )

    # 3. USAspending
    logger.info("ingestion_step", step=2, total=4, source="usaspending")
    source_started = datetime.now(timezone.utc)
    results["usaspending"] = ingest_usaspending()
    _write_pipeline_run("usaspending", results["usaspending"], source_started)
    logger.info(
        "ingestion_step_complete",
        source="usaspending",
        status=results["usaspending"].get("status"),
        records_processed=results["usaspending"].get("records_processed", 0),
        records_added=results["usaspending"].get("records_added", 0),
        records_updated=results["usaspending"].get("records_updated", 0),
        records_failed=results["usaspending"].get("records_failed", 0),
    )

    # 4. SBIR
    logger.info("ingestion_step", step=3, total=4, source="sbir")
    source_started = datetime.now(timezone.utc)
    results["sbir"] = ingest_sbir()
    _write_pipeline_run("sbir", results["sbir"], source_started)
    logger.info(
        "ingestion_step_complete",
        source="sbir",
        status=results["sbir"].get("status"),
        records_processed=results["sbir"].get("records_processed", 0),
        records_added=results["sbir"].get("records_added", 0),
        records_updated=results["sbir"].get("records_updated", 0),
        records_failed=results["sbir"].get("records_failed", 0),
    )

    # 5. SAM.gov (incremental, skipped if no API key)
    logger.info("ingestion_step", step=4, total=4, source="sam_gov")
    source_started = datetime.now(timezone.utc)
    results["sam_gov"] = ingest_sam_gov()
    _write_pipeline_run("sam_gov", results["sam_gov"], source_started)
    logger.info(
        "ingestion_step_complete",
        source="sam_gov",
        status=results["sam_gov"].get("status"),
        records_processed=results["sam_gov"].get("records_processed", 0),
        records_added=results["sam_gov"].get("records_added", 0),
        records_updated=results["sam_gov"].get("records_updated", 0),
        records_failed=results["sam_gov"].get("records_failed", 0),
    )

    # 6. Summary
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    summary = {
        "sources": results,
        "elapsed_seconds": round(elapsed, 1),
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    total_processed = sum(r.get("records_processed", 0) for r in results.values())
    total_added = sum(r.get("records_added", 0) for r in results.values())
    total_updated = sum(r.get("records_updated", 0) for r in results.values())
    failures = [name for name, r in results.items() if r.get("status") not in ("success", "skipped")]

    summary["total_processed"] = total_processed
    summary["total_added"] = total_added
    summary["total_updated"] = total_updated
    summary["failures"] = failures

    logger.info(
        "ingestion_run_complete",
        elapsed_seconds=summary["elapsed_seconds"],
        total_processed=total_processed,
        total_added=total_added,
        total_updated=total_updated,
        failures=failures,
    )

    # 7. Staleness check — alert if any source missed its window
    from grantflow.pipeline.monitor import check_staleness
    stale_sources = check_staleness()
    if stale_sources:
        summary["stale_sources"] = stale_sources
        logger.warning("stale_sources_after_run", sources=stale_sources)
    else:
        logger.info("all_sources_fresh")

    return summary


def main():
    """CLI entry point for running all ingestion."""
    configure_structlog(env=os.getenv("GRANTFLOW_ENV", "development"))

    print("\n" + "=" * 60)
    print("  GrantFlow Data Ingestion Pipeline")
    print("=" * 60 + "\n")

    summary = run_all_ingestion()

    print("\n" + "=" * 60)
    print("  INGESTION SUMMARY")
    print("=" * 60)
    print(f"  Elapsed:    {summary['elapsed_seconds']}s")
    print(f"  Processed:  {summary['total_processed']}")
    print(f"  Added:      {summary['total_added']}")
    print(f"  Updated:    {summary['total_updated']}")

    for source, result in summary["sources"].items():
        status_icon = "OK" if result.get("status") == "success" else "FAIL"
        print(f"  {source:15s} [{status_icon}] "
              f"{result.get('records_processed', 0)} processed, "
              f"{result.get('records_added', 0)} added, "
              f"{result.get('records_updated', 0)} updated")
        if result.get("error"):
            print(f"    Error: {result['error'][:100]}")

    if summary["failures"]:
        print(f"\n  FAILURES: {', '.join(summary['failures'])}")

    print("=" * 60 + "\n")
    return summary


if __name__ == "__main__":
    main()
