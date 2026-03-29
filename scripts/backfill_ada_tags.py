"""Backfill ada-compliance topic tags for ADA/accessibility grants.

Scans all opportunities and tags matching records with "ada-compliance"
in the topic_tags column. Safe to run multiple times (idempotent).

Run with:
    uv run python scripts/backfill_ada_tags.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from grantflow.database import SessionLocal
from grantflow.pipeline.ada_tagger import run_ada_backfill
from sqlalchemy import text


def main() -> int:
    session = SessionLocal()
    try:
        total_before = session.execute(
            text(
                "SELECT COUNT(*) FROM opportunities WHERE topic_tags LIKE '%ada-compliance%'"
            )
        ).scalar()

        print(f"ADA-tagged grants before backfill: {total_before}")
        print("Running ADA backfill...")

        updated = run_ada_backfill(db=session)

        total_after = session.execute(
            text(
                "SELECT COUNT(*) FROM opportunities WHERE topic_tags LIKE '%ada-compliance%'"
            )
        ).scalar()

        print(f"Updated: {updated} rows tagged with 'ada-compliance'")
        print(f"ADA-tagged grants after backfill: {total_after}")

        sample = session.execute(
            text(
                "SELECT id, title FROM opportunities "
                "WHERE topic_tags LIKE '%ada-compliance%' "
                "ORDER BY id LIMIT 10"
            )
        ).fetchall()
        if sample:
            print("\nSample tagged grants:")
            for row_id, title in sample:
                print(f"  {row_id}: {title}")

        return updated
    finally:
        session.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
