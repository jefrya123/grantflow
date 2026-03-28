"""Canonical ID generation and cross-source deduplication for grant opportunities."""

import hashlib
import re

from sqlalchemy import text
from sqlalchemy.orm import Session


def make_canonical_id(opportunity: dict) -> str:
    """Generate a deterministic canonical ID for a grant opportunity dict.

    Primary key: opportunity_number (normalized: stripped, uppercased, hyphens/spaces collapsed).
    Fallback: cfda_numbers + agency_code + close_date (normalized to lowercase, stripped).

    Returns: "canon_" + sha256(normalized_key)[:16]
    """
    opp_number = opportunity.get("opportunity_number") or ""
    opp_number = opp_number.strip()

    if opp_number:
        # Normalize: uppercase, collapse runs of hyphens/spaces to single hyphen
        normalized = opp_number.upper()
        normalized = re.sub(r"[-\s]+", "-", normalized)
        key = normalized
    else:
        # Fallback: cfda_numbers + agency_code + close_date
        cfda = (opportunity.get("cfda_numbers") or "").strip().lower()
        agency = (opportunity.get("agency_code") or "").strip().lower()
        close = (opportunity.get("close_date") or "").strip().lower()
        key = f"{cfda}|{agency}|{close}"

    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"canon_{digest[:16]}"


def find_duplicate_groups(session: Session) -> list[dict]:
    """Find all canonical_id groups with more than one opportunity (cross-source duplicates).

    Read-only — does NOT modify any data.

    Returns list of dicts: {"canonical_id": str, "count": int, "ids": list[str], "sources": list[str]}
    """
    sql = text("""
        SELECT
            canonical_id,
            count(*) AS count,
            array_agg(id) AS ids,
            array_agg(source) AS sources
        FROM opportunities
        GROUP BY canonical_id
        HAVING count(*) > 1
    """)
    rows = session.execute(sql)
    results = []
    for row in rows:
        results.append(
            {
                "canonical_id": row.canonical_id,
                "count": row.count,
                "ids": list(row.ids) if row.ids else [],
                "sources": list(row.sources) if row.sources else [],
            }
        )
    return results


def assign_canonical_ids(session: Session) -> dict:
    """Assign canonical_id to every Opportunity where canonical_id IS NULL.

    Uses raw SQL to select only required columns, avoiding TSVECTORType
    compatibility issues on SQLite (search_vector exists in model but not
    in SQLite schema — raw SQL bypasses the full-column ORM SELECT).

    Commits in batches of 1000.
    Returns stats: {"assigned": int, "already_set": int}
    """
    batch_size = 1000

    # Count already-set records for stats (raw SQL to avoid ORM schema issues)
    already_set = (
        session.execute(
            text("SELECT count(*) FROM opportunities WHERE canonical_id IS NOT NULL")
        ).scalar()
        or 0
    )

    # Fetch only the columns needed for canonical ID generation
    null_rows = session.execute(
        text(
            "SELECT id, opportunity_number, cfda_numbers, agency_code, close_date "
            "FROM opportunities WHERE canonical_id IS NULL"
        )
    ).fetchall()

    assigned = 0
    batch_updates: list[dict] = []

    for row in null_rows:
        canon_id = make_canonical_id(
            {
                "opportunity_number": row.opportunity_number,
                "cfda_numbers": row.cfda_numbers,
                "agency_code": row.agency_code,
                "close_date": row.close_date,
            }
        )
        batch_updates.append({"row_id": row.id, "canon_id": canon_id})
        assigned += 1

        if len(batch_updates) >= batch_size:
            session.execute(
                text(
                    "UPDATE opportunities SET canonical_id = :canon_id WHERE id = :row_id"
                ),
                batch_updates,
            )
            session.commit()
            batch_updates = []

    if batch_updates:
        session.execute(
            text(
                "UPDATE opportunities SET canonical_id = :canon_id WHERE id = :row_id"
            ),
            batch_updates,
        )
        session.commit()

    return {"assigned": assigned, "already_set": already_set}
