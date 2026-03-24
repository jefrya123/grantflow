from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from grantflow.models import Opportunity, Award
from grantflow.database import get_db
from grantflow.config import BASE_DIR

router = APIRouter()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/")
def index():
    return RedirectResponse(url="/search", status_code=302)


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
    sort: str = "post_date",
    order: str = "desc",
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from sqlalchemy import text

    query = db.query(Opportunity)

    if q:
        fts_query = text(
            "SELECT rowid FROM opportunities_fts WHERE opportunities_fts MATCH :q"
        )
        fts_rowids = db.execute(fts_query, {"q": q}).fetchall()
        rowids = [r[0] for r in fts_rowids]
        if not rowids:
            return templates.TemplateResponse("search.html", {
                "request": request,
                "results": [],
                "total": 0,
                "page": 1,
                "per_page": per_page,
                "pages": 0,
                "filters": _build_filters(q, status, source, agency, category,
                                          eligible, min_award, max_award,
                                          closing_after, closing_before, sort, order),
            })
        query = query.filter(
            text(f"opportunities.rowid IN ({','.join(str(r) for r in rowids)})")
        )

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

    return templates.TemplateResponse(request, "search.html", context={
        "results": results,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "filters": _build_filters(q, status, source, agency, category,
                                  eligible, min_award, max_award,
                                  closing_after, closing_before, sort, order),
    })


@router.get("/opportunity/{opportunity_id}")
def detail_page(
    request: Request,
    opportunity_id: str,
    db: Session = Depends(get_db),
):
    from fastapi import HTTPException

    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    awards = []
    if opp.opportunity_number:
        awards = db.query(Award).filter(
            Award.opportunity_number == opp.opportunity_number
        ).all()
    if not awards and opp.cfda_numbers:
        awards = db.query(Award).filter(
            Award.cfda_numbers.ilike(f"%{opp.cfda_numbers}%")
        ).all()

    return templates.TemplateResponse(request, "detail.html", context={
        "opp": opp,
        "awards": awards,
    })


def _build_filters(q, status, source, agency, category, eligible,
                   min_award, max_award, closing_after, closing_before,
                   sort, order):
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
    }
