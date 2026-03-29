import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from grantflow.models import Opportunity, Award
from grantflow.database import get_db
from grantflow.config import BASE_DIR, DATABASE_URL as _DB_URL

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    total_opps = db.query(func.count(Opportunity.id)).scalar() or 0
    return templates.TemplateResponse(
        request,
        "landing.html",
        context={
            "total_opps": total_opps,
        },
    )


@router.get("/pricing")
def pricing_page(request: Request):
    return templates.TemplateResponse(request, "pricing.html", context={})


@router.get("/playground")
def playground_page(request: Request):
    demo_api_key = os.getenv("GRANTFLOW_DEMO_API_KEY", "")
    return templates.TemplateResponse(
        request,
        "playground.html",
        context={
            "demo_api_key": demo_api_key,
        },
    )


@router.get("/search")
def search_page(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    source: str | None = None,
    agency: str | None = None,
    category: str | None = None,
    eligible: str | None = None,
    min_award: float | None = None,
    max_award: float | None = None,
    closing_after: str | None = None,
    closing_before: str | None = None,
    topic: str | None = None,
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
                Opportunity.search_vector.op("@@")(func.to_tsquery("english", q))
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

    if status:
        query = query.filter(Opportunity.opportunity_status == status)
    if source:
        query = query.filter(Opportunity.source == source)
    if agency:
        query = query.filter(Opportunity.agency_code.ilike(f"%{agency}%"))
    if category:
        query = query.filter(Opportunity.category == category)
    if eligible:
        query = query.filter(Opportunity.eligible_applicants.ilike(f"%{eligible}%"))
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

    total = query.count()

    allowed_sort_fields = {
        "post_date": Opportunity.post_date,
        "close_date": Opportunity.close_date,
        "title": Opportunity.title,
        "award_ceiling": Opportunity.award_ceiling,
    }
    sort_col = allowed_sort_fields.get(sort, Opportunity.post_date)
    if order == "asc":
        query = query.order_by(sort_col.asc().nullslast())
    else:
        query = query.order_by(sort_col.desc().nullslast())

    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    results = query.offset(offset).limit(per_page).all()

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closing_soon_str = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )

    return templates.TemplateResponse(
        request,
        "search.html",
        context={
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "filters": _build_filters(
                q,
                status,
                source,
                agency,
                category,
                eligible,
                min_award,
                max_award,
                closing_after,
                closing_before,
                sort,
                order,
                topic,
            ),
            "now_date": today_str,
            "closing_soon_date": closing_soon_str,
        },
    )


@router.get("/opportunity/{opportunity_id}")
def detail_page(
    request: Request,
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    awards = []
    if opp.opportunity_number:
        awards = (
            db.query(Award)
            .filter(Award.opportunity_number == opp.opportunity_number)
            .all()
        )
    if not awards and opp.cfda_numbers:
        awards = (
            db.query(Award)
            .filter(Award.cfda_numbers.ilike(f"%{opp.cfda_numbers}%"))
            .all()
        )

    return templates.TemplateResponse(
        request,
        "detail.html",
        context={
            "opp": opp,
            "awards": awards,
        },
    )


def _build_filters(
    q,
    status,
    source,
    agency,
    category,
    eligible,
    min_award,
    max_award,
    closing_after,
    closing_before,
    sort,
    order,
    topic=None,
):
    return {
        "q": q or "",
        "status": status or "",
        "source": source or "",
        "agency": agency or "",
        "category": category or "",
        "eligible": eligible or "",
        "min_award": min_award or "",
        "max_award": max_award or "",
        "closing_after": closing_after or "",
        "closing_before": closing_before or "",
        "sort": sort,
        "order": order,
        "topic": topic or "",
    }


@router.get("/agency/{slug}")
def agency_page(
    request: Request,
    slug: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    # Match by agency_code (case-insensitive) or fall back to agency_name slug
    query = db.query(Opportunity).filter(
        func.lower(Opportunity.agency_code) == slug.lower()
    )
    # Determine display name and code from first result
    sample = query.first()
    if not sample:
        raise HTTPException(status_code=404, detail="Agency not found")

    agency_name = sample.agency_name or sample.agency_code or slug.upper()
    agency_code = sample.agency_code

    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    results = (
        query.order_by(Opportunity.post_date.desc().nullslast())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "agency.html",
        context={
            "slug": slug,
            "agency_name": agency_name,
            "agency_code": agency_code,
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        },
    )


@router.get("/ada-grants")
def ada_grants_redirect():
    return RedirectResponse("/fund-your-fix", status_code=301)


@router.get("/fund-your-fix")
def fund_your_fix_page(
    request: Request,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    municipality: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Opportunity).filter(
        Opportunity.topic_tags.ilike("%ada-compliance%")
    )

    if municipality:
        slug_term = f"%{municipality}%"
        muni_query = query.filter(
            or_(
                Opportunity.eligible_applicants.ilike(slug_term),
                Opportunity.description.ilike(slug_term),
            )
        )
        if muni_query.count() > 0:
            query = muni_query

    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    results = (
        query.order_by(Opportunity.close_date.asc().nullslast())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Featured grant: pin FTA "All Stations Access" grant when present, else soonest closing
    fta_grant = (
        db.query(Opportunity)
        .filter(
            Opportunity.topic_tags.ilike('%"ada-compliance"%'),
            Opportunity.title.ilike("%all stations%"),
        )
        .order_by(Opportunity.close_date.asc().nullslast())
        .first()
    )
    featured = fta_grant if fta_grant else (results[0] if results else None)
    featured_is_fta = fta_grant is not None and featured == fta_grant

    today = datetime.now(timezone.utc).date()
    days_until_close = None
    if featured and featured.close_date:
        try:
            close = datetime.strptime(featured.close_date, "%Y-%m-%d").date()
            days_until_close = (close - today).days
        except ValueError:
            pass

    return templates.TemplateResponse(
        request,
        "fund_your_fix.html",
        context={
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
            "featured": featured,
            "days_until_close": days_until_close,
            "municipality": municipality,
            "featured_is_fta": featured_is_fta,
        },
    )


@router.get("/fund-your-fix/widget")
def fund_your_fix_widget(
    request: Request,
    db: Session = Depends(get_db),
):
    results = (
        db.query(Opportunity)
        .filter(Opportunity.topic_tags.ilike('%"ada-compliance"%'))
        .order_by(Opportunity.close_date.asc().nullslast())
        .limit(5)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "fund_your_fix_widget.html",
        context={"results": results},
    )


@router.get("/stats")
def stats_page(request: Request, db: Session = Depends(get_db)):
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closing_soon_str = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )

    total = db.query(Opportunity).count()

    by_source_rows = (
        db.query(Opportunity.source, func.count(Opportunity.id).label("count"))
        .group_by(Opportunity.source)
        .all()
    )
    by_source = [
        {"source": row.source or "unknown", "count": row.count}
        for row in by_source_rows
    ]

    closing_soon = (
        db.query(Opportunity)
        .filter(
            Opportunity.close_date >= today_str,
            Opportunity.close_date <= closing_soon_str,
        )
        .count()
    )

    top_agency_rows = (
        db.query(Opportunity.agency_name, func.count(Opportunity.id).label("count"))
        .filter(Opportunity.agency_name.isnot(None))
        .group_by(Opportunity.agency_name)
        .order_by(func.count(Opportunity.id).desc())
        .limit(10)
        .all()
    )
    top_agencies = [
        {"agency_name": row.agency_name, "count": row.count} for row in top_agency_rows
    ]

    return templates.TemplateResponse(
        request,
        "stats.html",
        context={
            "total": total,
            "by_source": by_source,
            "closing_soon": closing_soon,
            "top_agencies": top_agencies,
        },
    )
