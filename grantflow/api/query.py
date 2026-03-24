"""
Shared query builder for Opportunity filtering.

Extracted from search_opportunities to eliminate duplication between
the search and export endpoints.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from grantflow.models import Opportunity
from grantflow.config import DATABASE_URL as _DB_URL


def build_opportunity_query(
    db: Session,
    q: str | None = None,
    status: str | None = None,
    agency: str | None = None,
    eligible: str | None = None,
    category: str | None = None,
    source: str | None = None,
    min_award: float | None = None,
    max_award: float | None = None,
    closing_after: str | None = None,
    closing_before: str | None = None,
    topic: str | None = None,
):
    """
    Build an unsorted, unpaginated SQLAlchemy query for Opportunity rows.

    Applies full-text search (PostgreSQL tsvector or SQLite LIKE fallback)
    and all standard filter parameters. Sort and pagination are left to
    the caller.

    Returns a SQLAlchemy Query object.
    """
    if q:
        if _DB_URL.startswith("postgresql") or _DB_URL.startswith("postgres"):
            # PostgreSQL: use tsvector GIN index
            query = db.query(Opportunity).filter(
                Opportunity.search_vector.op("@@")(
                    func.to_tsquery("english", q)
                )
            )
        else:
            # SQLite fallback: LIKE search (no GIN index, dev/test only)
            query = db.query(Opportunity).filter(
                Opportunity.title.ilike(f"%{q}%")
                | Opportunity.description.ilike(f"%{q}%")
                | Opportunity.agency_name.ilike(f"%{q}%")
            )
    else:
        query = db.query(Opportunity)

    # Apply filters
    if status:
        query = query.filter(Opportunity.opportunity_status == status)
    if agency:
        query = query.filter(Opportunity.agency_code.ilike(f"%{agency}%"))
    if eligible:
        query = query.filter(Opportunity.eligible_applicants.ilike(f"%{eligible}%"))
    if category:
        query = query.filter(Opportunity.category == category)
    if source:
        query = query.filter(Opportunity.source == source)
    if min_award is not None:
        query = query.filter(Opportunity.award_floor >= min_award)
    if max_award is not None:
        query = query.filter(Opportunity.award_ceiling <= max_award)
    if closing_after:
        query = query.filter(Opportunity.close_date >= closing_after)
    if closing_before:
        query = query.filter(Opportunity.close_date <= closing_before)
    if topic:
        query = query.filter(Opportunity.topic_tags.ilike(f'%"{topic}"%'))

    return query
