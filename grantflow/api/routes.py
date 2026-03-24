from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from datetime import datetime, timedelta, timezone

from grantflow.models import Opportunity, Award, Agency, IngestionLog
from grantflow.database import get_db
from grantflow.config import DATABASE_URL as _DB_URL

router = APIRouter(prefix="/api/v1")


@router.get("/opportunities/search")
def search_opportunities(
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
    sort: str = "post_date",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if q:
        if _DB_URL.startswith("postgresql") or _DB_URL.startswith("postgres"):
            # PostgreSQL: use tsvector GIN index
            query = db.query(Opportunity).filter(
                Opportunity.search_vector.op("@@")(
                    func.to_tsquery("english", q)
                )
            )
        else:
            # SQLite fallback: LIKE search (no GIN index, dev-only)
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

    # Count total before pagination
    total = query.count()

    # Sort
    allowed_sort_fields = {
        "post_date": Opportunity.post_date,
        "close_date": Opportunity.close_date,
        "title": Opportunity.title,
        "award_ceiling": Opportunity.award_ceiling,
        "award_floor": Opportunity.award_floor,
        "last_updated": Opportunity.last_updated,
    }
    sort_col = allowed_sort_fields.get(sort, Opportunity.post_date)
    if order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    # Paginate
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    results = query.offset(offset).limit(per_page).all()

    return {
        "results": [_opportunity_to_dict(o) for o in results],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: str, db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    result = _opportunity_to_dict(opp)

    # Find linked awards by opportunity_number or cfda_numbers
    awards = []
    if opp.opportunity_number:
        awards = db.query(Award).filter(
            Award.opportunity_number == opp.opportunity_number
        ).all()
    if not awards and opp.cfda_numbers:
        awards = db.query(Award).filter(
            Award.cfda_numbers.ilike(f"%{opp.cfda_numbers}%")
        ).all()

    result["awards"] = [_award_to_dict(a) for a in awards]
    return result


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_opportunities = db.query(func.count(Opportunity.id)).scalar() or 0

    # By source
    by_source_rows = db.query(
        Opportunity.source, func.count(Opportunity.id)
    ).group_by(Opportunity.source).all()
    by_source = {row[0]: row[1] for row in by_source_rows}

    # By status
    by_status_rows = db.query(
        Opportunity.opportunity_status, func.count(Opportunity.id)
    ).group_by(Opportunity.opportunity_status).all()
    by_status = {(row[0] or "unknown"): row[1] for row in by_status_rows}

    # Awards
    total_awards = db.query(func.count(Award.id)).scalar() or 0
    total_award_dollars = db.query(func.sum(Award.award_amount)).scalar() or 0

    # Closing soon (next 30 days)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    thirty_days = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
    closing_soon = db.query(func.count(Opportunity.id)).filter(
        Opportunity.close_date >= today,
        Opportunity.close_date <= thirty_days,
    ).scalar() or 0

    # Top agencies
    top_agencies_rows = db.query(
        Opportunity.agency_name, func.count(Opportunity.id).label("count")
    ).group_by(Opportunity.agency_name).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()
    top_agencies = [{"agency": row[0], "count": row[1]} for row in top_agencies_rows]

    return {
        "total_opportunities": total_opportunities,
        "by_source": by_source,
        "by_status": by_status,
        "total_awards": total_awards,
        "total_award_dollars": total_award_dollars,
        "closing_soon": closing_soon,
        "top_agencies": top_agencies,
    }


@router.get("/agencies")
def get_agencies(db: Session = Depends(get_db)):
    rows = db.query(
        Opportunity.agency_code,
        Opportunity.agency_name,
        func.count(Opportunity.id).label("count"),
    ).group_by(
        Opportunity.agency_code, Opportunity.agency_name
    ).order_by(
        func.count(Opportunity.id).desc()
    ).all()

    return [
        {"code": row[0], "name": row[1], "opportunity_count": row[2]}
        for row in rows
    ]


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Returns pipeline freshness and record counts per source."""
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=48)

    # Most recent IngestionLog per source (highest id = most recent row)
    from sqlalchemy import select
    latest_ids_stmt = (
        select(func.max(IngestionLog.id).label("max_id"))
        .group_by(IngestionLog.source)
    )
    latest_logs = (
        db.query(IngestionLog)
        .filter(IngestionLog.id.in_(latest_ids_stmt))
        .all()
    )

    # Record counts per source
    count_rows = (
        db.query(Opportunity.source, func.count(Opportunity.id))
        .group_by(Opportunity.source)
        .all()
    )
    counts_by_source = {row[0]: row[1] for row in count_rows}

    sources = {}
    overall_stale = False

    for log in latest_logs:
        is_stale = False
        if log.completed_at and log.status == "success":
            try:
                completed = datetime.fromisoformat(log.completed_at.replace("Z", "+00:00"))
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
                if completed < stale_threshold:
                    is_stale = True
                    overall_stale = True
            except (ValueError, AttributeError):
                pass

        sources[log.source] = {
            "last_ingestion_at": log.completed_at,
            "last_status": log.status,
            "records_added_last_run": log.records_added,
            "record_count": counts_by_source.get(log.source, 0),
            "stale": is_stale,
        }

    return {
        "status": "stale" if overall_stale else "ok",
        "sources": sources,
        "checked_at": now.isoformat(),
    }


def _opportunity_to_dict(o: Opportunity) -> dict:
    return {
        "id": o.id,
        "source": o.source,
        "source_id": o.source_id,
        "title": o.title,
        "description": o.description,
        "agency_code": o.agency_code,
        "agency_name": o.agency_name,
        "opportunity_number": o.opportunity_number,
        "opportunity_status": o.opportunity_status,
        "funding_instrument": o.funding_instrument,
        "category": o.category,
        "cfda_numbers": o.cfda_numbers,
        "eligible_applicants": o.eligible_applicants,
        "post_date": o.post_date,
        "close_date": o.close_date,
        "last_updated": o.last_updated,
        "award_floor": o.award_floor,
        "award_ceiling": o.award_ceiling,
        "estimated_total_funding": o.estimated_total_funding,
        "expected_number_of_awards": o.expected_number_of_awards,
        "cost_sharing_required": o.cost_sharing_required,
        "contact_email": o.contact_email,
        "contact_text": o.contact_text,
        "additional_info_url": o.additional_info_url,
        "source_url": o.source_url,
    }


def _award_to_dict(a: Award) -> dict:
    return {
        "id": a.id,
        "award_id": a.award_id,
        "title": a.title,
        "recipient_name": a.recipient_name,
        "award_amount": a.award_amount,
        "award_date": a.award_date,
        "agency_name": a.agency_name,
        "place_state": a.place_state,
        "place_city": a.place_city,
    }
