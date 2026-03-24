"""Normalize CFDA numbers and link Opportunities to Awards cross-source."""

import re

from sqlalchemy.orm import Session

from grantflow.database import SessionLocal
from grantflow.models import Opportunity, Award
from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("cfda_link")


def normalize_cfda(raw: str | None) -> str:
    """Normalize a CFDA/ALN number to canonical 'prefix.suffix' format.

    Input variants handled:
        "84.007"  → "84.007"   (already canonical)
        "84-007"  → "84.007"   (hyphen separator)
        "084.007" → "84.007"   (leading zero in prefix)
        "84.7"    → "84.007"   (suffix not zero-padded)
        "84 007"  → "84.007"   (space separator)
        "  84.007  " → "84.007" (whitespace)
        None / ""  → ""         (empty / null input)

    Returns canonical string or empty string if input is None/empty.
    """
    if not raw:
        return ""
    raw = raw.strip()
    if not raw:
        return ""

    # Replace hyphens and spaces with dots
    normalized = re.sub(r"[-\s]+", ".", raw)

    # Split on dot
    parts = normalized.split(".")
    if len(parts) != 2:
        return raw.strip()  # can't normalize, return original stripped

    prefix, suffix = parts

    # Remove leading zeros from prefix (84, not 084)
    prefix = str(int(prefix)) if prefix.isdigit() else prefix

    # Zero-pad suffix to 3 digits
    suffix = suffix.zfill(3) if suffix.isdigit() else suffix

    return f"{prefix}.{suffix}"


def link_opportunities_to_awards(session: Session | None = None) -> dict:
    """Normalize CFDA numbers in-place and find Opportunity→Award cross-links.

    Steps:
    1. Load all Opportunities with non-empty cfda_numbers.
    2. Normalize each CFDA value; update if changed.
    3. For each opportunity, find Awards whose cfda_numbers overlap.
    4. Log and return match statistics.

    Returns:
        {
            "opportunities_processed": int,
            "cfda_normalized": int,      # rows whose cfda_numbers were updated
            "award_links_found": int,    # total award records matched
        }
    """
    own_session = session is None
    if own_session:
        session = SessionLocal()

    try:
        opportunities_processed = 0
        cfda_normalized = 0
        award_links_found = 0

        # 1. Fetch opportunities with CFDA data
        opps = (
            session.query(Opportunity)
            .filter(
                Opportunity.cfda_numbers.isnot(None),
                Opportunity.cfda_numbers != "",
            )
            .all()
        )

        for opp in opps:
            opportunities_processed += 1

            # 2. Normalize each comma-separated CFDA value
            raw_values = [v.strip() for v in opp.cfda_numbers.split(",") if v.strip()]
            normalized_values = [normalize_cfda(v) for v in raw_values]
            normalized_str = ", ".join(v for v in normalized_values if v)

            if normalized_str != opp.cfda_numbers:
                opp.cfda_numbers = normalized_str
                cfda_normalized += 1

            # 3. Find matching awards using exact-match contains
            # Awards store CFDA in the same field format; normalized values allow
            # reliable string contains match. Full GIN index is a Phase 4 concern.
            for norm_cfda in normalized_values:
                if not norm_cfda:
                    continue
                matched = (
                    session.query(Award)
                    .filter(Award.cfda_numbers.contains(norm_cfda))
                    .count()
                )
                award_links_found += matched

        if own_session:
            session.commit()

        stats = {
            "opportunities_processed": opportunities_processed,
            "cfda_normalized": cfda_normalized,
            "award_links_found": award_links_found,
        }
        logger.info(
            "cfda_link_complete",
            opportunities_processed=opportunities_processed,
            cfda_normalized=cfda_normalized,
            award_links_found=award_links_found,
        )
        return stats

    except Exception as exc:
        if own_session:
            session.rollback()
        logger.error("cfda_link_failed", error=str(exc))
        raise
    finally:
        if own_session:
            session.close()
