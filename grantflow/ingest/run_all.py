"""Orchestrator that runs all data ingestion pipelines."""

import logging
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from grantflow.database import init_db, engine
from grantflow.ingest.grants_gov import ingest_grants_gov
from grantflow.ingest.usaspending import ingest_usaspending
from grantflow.ingest.sbir import ingest_sbir
from grantflow.pipeline.logging import configure_structlog

logger = logging.getLogger(__name__)



def run_all_ingestion() -> dict:
    """Run all ingestion pipelines in sequence. Returns summary stats."""
    started = datetime.now(timezone.utc)
    logger.info("Starting full ingestion run at %s", started.isoformat())

    # 1. Initialize database
    init_db()

    results = {}

    # 2. Grants.gov
    logger.info("=" * 60)
    logger.info("STEP 1/3: Grants.gov XML extract")
    logger.info("=" * 60)
    results["grants_gov"] = ingest_grants_gov()

    # 3. USAspending
    logger.info("=" * 60)
    logger.info("STEP 2/3: USAspending.gov API")
    logger.info("=" * 60)
    results["usaspending"] = ingest_usaspending()

    # 4. SBIR
    logger.info("=" * 60)
    logger.info("STEP 3/3: SBIR awards & solicitations")
    logger.info("=" * 60)
    results["sbir"] = ingest_sbir()

    # 5. Summary
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
    failures = [name for name, r in results.items() if r.get("status") != "success"]

    summary["total_processed"] = total_processed
    summary["total_added"] = total_added
    summary["total_updated"] = total_updated
    summary["failures"] = failures

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
