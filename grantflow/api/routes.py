import csv
import io

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_
from datetime import datetime, timedelta, timezone

from grantflow.models import Opportunity, Award, Agency, IngestionLog, ApiKey
from grantflow.database import get_db
from grantflow.config import DATABASE_URL as _DB_URL
from grantflow.pipeline.monitor import get_freshness_report
from grantflow.api.auth import get_api_key
from grantflow.api.query import build_opportunity_query
from grantflow.api.schemas import (
    OpportunityResponse,
    OpportunityDetailResponse,
    AwardResponse,
    SearchResponse,
    StatsResponse,
)
from grantflow.app import limiter

router = APIRouter(prefix="/api/v1")


@router.get("/opportunities/search", response_model=SearchResponse, tags=["opportunities"])
@limiter.limit("1000/day")
def search_opportunities(
    request: Request,
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
    api_key: ApiKey = Depends(get_api_key),
) -> SearchResponse:
    query = build_opportunity_query(
        db,
        q=q,
        status=status,
        agency=agency,
        eligible=eligible,
        category=category,
        source=source,
        min_award=min_award,
        max_award=max_award,
        closing_after=closing_after,
        closing_before=closing_before,
    )

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

    return SearchResponse(
        results=[OpportunityResponse.model_validate(o) for o in results],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


_EXPORT_CSV_COLUMNS = [
    "id", "title", "agency_name", "source", "opportunity_status",
    "opportunity_number", "cfda_numbers", "post_date", "close_date",
    "award_floor", "award_ceiling", "source_url",
]


@router.get("/opportunities/export", tags=["opportunities"])
@limiter.limit("100/day")
def export_opportunities(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
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
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    """Bulk export of opportunities (max 10,000 rows). Requires API key."""
    query = build_opportunity_query(
        db,
        q=q,
        status=status,
        agency=agency,
        eligible=eligible,
        category=category,
        source=source,
        min_award=min_award,
        max_award=max_award,
        closing_after=closing_after,
        closing_before=closing_before,
    )
    results = query.limit(10_000).all()

    if format == "json":
        return JSONResponse(content={
            "results": [OpportunityResponse.model_validate(o).model_dump() for o in results],
            "total": len(results),
        })

    # CSV via streaming generator
    def csv_generator():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_EXPORT_CSV_COLUMNS)
        yield buf.getvalue()

        for opp in results:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([getattr(opp, col, None) for col in _EXPORT_CSV_COLUMNS])
            yield buf.getvalue()

    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=opportunities.csv"},
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetailResponse, tags=["opportunities"])
@limiter.limit("1000/day")
def get_opportunity(
    request: Request,
    opportunity_id: str,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> OpportunityDetailResponse:
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    result = OpportunityDetailResponse.model_validate(opp)

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

    result.awards = [AwardResponse.model_validate(a) for a in awards]
    return result


@router.get("/stats", response_model=StatsResponse, tags=["opportunities"])
@limiter.limit("1000/day")
def get_stats(
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
) -> StatsResponse:
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
    total_award_dollars = db.query(func.sum(Award.award_amount)).scalar() or 0.0

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

    return StatsResponse(
        total_opportunities=total_opportunities,
        by_source=by_source,
        by_status=by_status,
        total_awards=total_awards,
        total_award_dollars=float(total_award_dollars),
        closing_soon=closing_soon,
        top_agencies=top_agencies,
    )


@router.get("/agencies", tags=["opportunities"])
@limiter.limit("1000/day")
def get_agencies(
    request: Request,
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
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

    # Per-source freshness from PipelineRun table
    freshness = get_freshness_report(db)

    return {
        "status": "stale" if overall_stale else "ok",
        "sources": sources,
        "source_freshness": freshness,
        "checked_at": now.isoformat(),
    }
