"""ADA keyword matching module and backfill CLI script.

Tags all ADA/accessibility-related grants in the topic_tags column
of the opportunities table with the "ada-compliance" tag.

Usage:
    uv run python -m grantflow.pipeline.ada_tagger
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Keyword lists — all lowercase; matched as substrings within the respective field.
# Contextually qualified: no bare "ada" entry to prevent false positives.
# ---------------------------------------------------------------------------

ADA_TITLE_KEYWORDS: list[str] = [
    "americans with disabilities act",
    "ada compliance",
    "ada remediat",
    "ada transition",
    "ada access",
    "ada standards",
    "accessibility compliance",
    "transit accessibility",
    "accessible transit",
    "paratransit",
    "wheelchair",
    "curb cut",
    "pedestrian accessibility",
    "sidewalk accessibility",
    "all stations accessibility",
    "station accessibility",
    "rail accessibility",
    "bus accessibility",
    "accessible transportation",
    "disability remediation",
    "accessible facilities",
    "disability infrastructure",
    "fta accessibility",
    "disability access",
]

ADA_DESC_KEYWORDS: list[str] = [
    "americans with disabilities act",
    "ada compliance",
    "ada transition plan",
    "paratransit",
    "section 504",
    "wheelchair",
    "curb cut",
    "all stations accessibility",
    "transit accessibility",
    "accessible transit",
    "rehabilitation act",
    "disability remediation",
    "accessible facilities",
]

ADA_AGENCY_KEYWORDS: list[str] = [
    "federal transit administration",
    # NOTE: "office of special education" intentionally excluded per RESEARCH.md —
    # would tag IDEA/education grants, not ADA infrastructure compliance.
]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def _is_ada_match(
    title: Optional[str],
    description: Optional[str],
    agency_name: Optional[str],
) -> bool:
    """Return True if any ADA keyword matches its respective field.

    All comparisons are case-insensitive substring checks.
    Contextually qualified keywords prevent false positives on substrings
    like 'ada' inside 'adaptation', 'Adams', or 'academic'.
    """
    t = (title or "").lower()
    d = (description or "").lower()
    a = (agency_name or "").lower()

    for kw in ADA_TITLE_KEYWORDS:
        if kw in t:
            return True

    for kw in ADA_DESC_KEYWORDS:
        if kw in d:
            return True

    for kw in ADA_AGENCY_KEYWORDS:
        if kw in a:
            return True

    return False


def _parse_tags(raw: Optional[str]) -> list[str]:
    """Parse a JSON-encoded tag list from the topic_tags column.

    Returns an empty list for None, malformed JSON, or non-list JSON values.
    """
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        return []
    except (json.JSONDecodeError, ValueError):
        return []


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def run_ada_backfill(db: Optional[Session] = None) -> int:
    """Tag all ADA-matching opportunities with "ada-compliance".

    Args:
        db: Optional SQLAlchemy session. If None, a new SessionLocal() is
            created and closed on return.

    Returns:
        Number of rows updated.
    """
    close_db = False
    if db is None:
        from grantflow.database import SessionLocal

        db = SessionLocal()
        close_db = True

    updated = 0
    try:
        rows = db.execute(
            text(
                "SELECT id, title, description, agency_name, topic_tags "
                "FROM opportunities"
            )
        ).fetchall()

        for row in rows:
            row_id, title, description, agency_name, topic_tags_raw = row

            if not _is_ada_match(title, description, agency_name):
                continue

            tags = _parse_tags(topic_tags_raw)
            if "ada-compliance" not in tags:
                tags.append("ada-compliance")
                db.execute(
                    text(
                        "UPDATE opportunities "
                        "SET topic_tags = :tags "
                        "WHERE id = :id"
                    ),
                    {"tags": json.dumps(tags), "id": row_id},
                )
                updated += 1

        db.commit()
    finally:
        if close_db:
            db.close()

    return updated


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    count = run_ada_backfill()
    print(f"ADA backfill complete: {count} rows tagged with 'ada-compliance'")
