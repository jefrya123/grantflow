"""Backfill normalization on all existing Opportunity records.

Fixes raw codes stored before normalizers were wired into the ingestors:
  - eligible_applicants: bare code like "25" -> JSON array "["Others ..."]"
  - category: raw code like "D" -> "Discretionary"
  - funding_instrument: raw code like "CA" -> "Cooperative Agreement"

Run with:
    uv run python scripts/backfill_normalization.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from grantflow.database import SessionLocal
from grantflow.normalizers import (
    normalize_eligibility_codes,
    normalize_category,
    normalize_funding_instrument,
)

# Raw SQL used to avoid SQLAlchemy ORM including search_vector (tsvector) which
# does not exist in the SQLite schema — same pattern used in assign_canonical_ids.
_SELECT_SQL = text("""
    SELECT id, eligible_applicants, category, funding_instrument
    FROM opportunities
    ORDER BY id
    LIMIT :limit OFFSET :offset
""")

_UPDATE_SQL = text("""
    UPDATE opportunities
    SET eligible_applicants = :eligible_applicants,
        category = :category,
        funding_instrument = :funding_instrument
    WHERE id = :id
""")


def backfill_normalization() -> dict:
    """Scan all Opportunity records and normalize raw codes to human-readable labels.

    Uses raw SQL to avoid SQLAlchemy ORM trying to SELECT search_vector
    (a tsvector column that doesn't exist in the SQLite schema).

    Returns a summary dict with keys: total_scanned, total_updated.
    """
    session = SessionLocal()
    batch_size = 500
    offset = 0
    total_scanned = 0
    total_updated = 0

    print("Starting normalization backfill...")

    try:
        while True:
            rows = session.execute(
                _SELECT_SQL, {"limit": batch_size, "offset": offset}
            ).fetchall()

            if not rows:
                break

            batch_updated = 0
            for row in rows:
                opp_id, eligible_applicants, category, funding_instrument = row
                changed = False
                new_elig = eligible_applicants
                new_cat = category
                new_fi = funding_instrument

                # Eligibility: re-normalize if stored as bare code (not a JSON array)
                if eligible_applicants and not eligible_applicants.startswith("["):
                    new_elig = normalize_eligibility_codes(eligible_applicants)
                    changed = True

                # Category: normalize if stored as short raw code (length <= 2)
                if category and len(category) <= 2:
                    normalized = normalize_category(category)
                    if normalized != category:
                        new_cat = normalized
                        changed = True

                # Funding instrument: normalize if stored as short raw code (length <= 2)
                if funding_instrument and len(funding_instrument) <= 2:
                    normalized = normalize_funding_instrument(funding_instrument)
                    if normalized != funding_instrument:
                        new_fi = normalized
                        changed = True

                if changed:
                    session.execute(
                        _UPDATE_SQL,
                        {
                            "id": opp_id,
                            "eligible_applicants": new_elig,
                            "category": new_cat,
                            "funding_instrument": new_fi,
                        },
                    )
                    batch_updated += 1

            session.commit()
            total_scanned += len(rows)
            total_updated += batch_updated
            offset += batch_size

            if total_scanned % 5000 == 0 or len(rows) < batch_size:
                print(
                    f"  Progress: scanned={total_scanned} updated={total_updated}"
                )

    finally:
        session.close()

    print(f"\nBackfill complete: total_scanned={total_scanned} total_updated={total_updated}")
    return {"total_scanned": total_scanned, "total_updated": total_updated}


if __name__ == "__main__":
    result = backfill_normalization()
    sys.exit(0)
