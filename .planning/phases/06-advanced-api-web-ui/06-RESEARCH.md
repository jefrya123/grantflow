# Phase 6: Advanced API + Web UI - Research

**Researched:** 2026-03-24
**Domain:** FastAPI bulk export, Jinja2 UI enhancement, PostgreSQL aggregation queries
**Confidence:** HIGH

---

## Summary

Phase 6 is fundamentally an enhancement phase, not a greenfield build. The entire stack — FastAPI, SQLAlchemy, Jinja2 templates, Pydantic v2 schemas, slowapi rate limiting, and the test harness — is already in place and proven across five prior phases. The codebase audit reveals that **most of the Phase 6 requirements are 60-80% implemented already**: search filtering exists, the detail page shows historical awards, the agencies endpoint exists, stats exist. What is missing are the closing-soon badge logic in templates, the bulk export endpoint, a stats dashboard web page, and polish/completion work on filters (agency and eligibility are missing from the search form filter row).

The phase splits cleanly into two orthogonal tracks that can be planned as separate waves within the phase: (1) API completion (bulk export, agencies schema, linked awards response model), and (2) Web UI completion (closing-soon badge, full filter exposure, stats page). No new dependencies are required. The only non-trivial technical decision is the CSV streaming approach for bulk export — Python's `csv` module with `StreamingResponse` is the right answer given the existing sync SQLAlchemy setup.

**Primary recommendation:** Use `StreamingResponse` + Python `csv.writer` for bulk export; add `now_date` to all Jinja2 template contexts for closing-soon badge logic; expose all existing API filters in the web search form.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-05 | Bulk export endpoint (CSV/JSON for search results) | StreamingResponse pattern; existing search query logic in api/routes.py reusable |
| API-06 | Historical awards linked in opportunity detail responses | Already implemented in GET /api/v1/opportunities/{id}; `awards` field exists in OpportunityDetailResponse; verify it's populated and test coverage exists |
| API-08 | Agencies endpoint with opportunity counts | Already implemented at GET /api/v1/agencies; needs Pydantic response_model added and test coverage |
| WEB-01 | Search page with filters (status, agency, category, eligibility, dates, award range) | Web route already supports all params; search.html filter row is missing agency, category, eligible, date, and award-range inputs |
| WEB-02 | Opportunity detail page with linked awards | Already implemented in detail.html; awards table renders when present |
| WEB-03 | "Closing soon" badge on opportunities closing within 30 days | Badge CSS class exists; template logic missing `now_date`; web route does not inject today's date |
| WEB-04 | Stats dashboard (total opps, by source, by agency, closing soon) | No /stats web page exists; GET /api/v1/stats backend logic complete; need new template + web route |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new deps needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | API routing, response models | Already in use |
| SQLAlchemy | >=2.0 | ORM queries, aggregations | Already in use |
| Pydantic v2 | >=2.0 | Response model validation | Already in use, ConfigDict(from_attributes=True) pattern established |
| Jinja2 | >=3.1 | Server-side HTML templates | Already in use via Jinja2Templates |
| Python stdlib `csv` | stdlib | CSV generation for bulk export | No dependency; handles quoting/escaping correctly |
| Python stdlib `io` | stdlib | StringIO/BytesIO buffer for CSV | Works with StreamingResponse |
| slowapi | >=0.1.9 | Rate limiting on export endpoint | Already in use; limiter imported from app.py |

### No New Dependencies Required

All Phase 6 functionality is achievable with the current dependency set. Do not add pandas, openpyxl, or any CSV library — Python's stdlib `csv` module is sufficient and introduces zero risk.

**Installation:** None required.

---

## Architecture Patterns

### What Already Exists (do not re-implement)

| Feature | Location | Status |
|---------|----------|--------|
| Search API with all filters | `grantflow/api/routes.py:search_opportunities` | Complete |
| Detail API with awards | `grantflow/api/routes.py:get_opportunity` | Complete |
| Stats API | `grantflow/api/routes.py:get_stats` | Complete |
| Agencies API | `grantflow/api/routes.py:get_agencies` | Exists, missing response_model |
| Web search page | `grantflow/web/routes.py:search_page` + `templates/search.html` | Route complete, template incomplete |
| Web detail page | `grantflow/web/routes.py:detail_page` + `templates/detail.html` | Complete |
| Pydantic schemas | `grantflow/api/schemas.py` | OpportunityResponse, StatsResponse, AwardResponse defined |
| Test harness | `tests/conftest.py` | SQLite in-memory, TestClient, db_session fixture |

### Gap Analysis: What Needs Building

**API gaps:**
1. `GET /api/v1/opportunities/export` — bulk export with same filter params as search, returns CSV or JSON (format param), requires API key, rate-limited
2. `GET /api/v1/agencies` — already exists but needs a `response_model=list[AgencyResponse]` Pydantic schema added (API-08 requires schema contract)

**Web UI gaps:**
1. `search.html` — add agency, category, eligible, closing_after, closing_before filter inputs to the filter row
2. `search.html` — add closing-soon badge: requires `now_date` injected from `web/routes.py:search_page`
3. New web route `GET /stats` + new `templates/stats.html` — stats dashboard page (API-04 already has the data)
4. `base.html` nav — add Stats link

### Pattern 1: Bulk Export via StreamingResponse

**What:** Reuse the exact search query from `search_opportunities`, strip pagination, stream output as CSV rows or JSON array.
**When to use:** Any endpoint that could return large result sets (thousands of rows).
**Why StreamingResponse:** The existing routes are sync (not async). `StreamingResponse` with a generator is the correct pattern — it does not buffer the full result set in memory.

```python
# Source: FastAPI official docs + stdlib csv
import csv
import io
from fastapi.responses import StreamingResponse

@router.get("/opportunities/export")
@limiter.limit("100/day")  # lower limit than search — export is expensive
def export_opportunities(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    # ... same filter params as search_opportunities ...
    db: Session = Depends(get_db),
    api_key: ApiKey = Depends(get_api_key),
):
    # Build query using identical filter logic as search_opportunities
    # (extract shared _build_opportunity_query() helper)
    query = _build_opportunity_query(db, q, status, agency, ...)
    results = query.limit(10_000).all()  # hard cap — no unbounded exports

    if format == "json":
        data = [OpportunityResponse.model_validate(o).model_dump() for o in results]
        return JSONResponse(content={"results": data, "total": len(data)})

    def csv_generator():
        buf = io.StringIO()
        writer = csv.writer(buf)
        # Header row
        writer.writerow(["id", "title", "agency_name", "source",
                         "opportunity_status", "close_date",
                         "award_floor", "award_ceiling", "post_date"])
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)
        for opp in results:
            writer.writerow([opp.id, opp.title, opp.agency_name, opp.source,
                              opp.opportunity_status, opp.close_date,
                              opp.award_floor, opp.award_ceiling, opp.post_date])
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    return StreamingResponse(
        csv_generator(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=opportunities.csv"},
    )
```

**CRITICAL: Route order matters.** `GET /opportunities/export` MUST be registered BEFORE `GET /opportunities/{opportunity_id}` in the router, or FastAPI will route `export` as an opportunity_id lookup. This is a known FastAPI gotcha with path parameter ambiguity.

### Pattern 2: Extract Shared Query Builder

**What:** The filter logic in `search_opportunities` (api/routes.py) and `search_page` (web/routes.py) is duplicated. Phase 6 adds a third consumer (export). Extract to a shared helper.

```python
# In grantflow/api/routes.py or a new grantflow/api/query.py
def _build_opportunity_query(
    db: Session,
    q: str | None,
    status: str | None,
    agency: str | None,
    eligible: str | None,
    category: str | None,
    source: str | None,
    min_award: float | None,
    max_award: float | None,
    closing_after: str | None,
    closing_before: str | None,
):
    # ... exact filter logic currently duplicated in both route files ...
```

**When to use:** Any time search filter logic is needed. Eliminates the drift risk between API and web search.

### Pattern 3: Closing-Soon Badge via Template Context

**What:** Pass today's date string into Jinja2 context from the route so the template can compare `opp.close_date` without calling Python builtins in the template.

```python
# In web/routes.py:search_page
from datetime import datetime, timedelta, timezone

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
thirty_days_str = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")

return templates.TemplateResponse(request, "search.html", context={
    "results": results,
    "now_date": today_str,
    "closing_soon_date": thirty_days_str,
    # ...
})
```

```jinja2
{# In search.html — closing-soon badge #}
{% if opp.close_date and opp.close_date >= now_date and opp.close_date <= closing_soon_date %}
<span class="badge badge-closing-soon">Closing Soon</span>
{% endif %}
```

Note: The template already has a stub for this logic (lines 66-68 in search.html) but `now_date` is never injected from the route. The fix is in the route, not the template.

### Pattern 4: AgencyResponse Pydantic Schema

**What:** Add a named response model for the agencies endpoint (currently returns raw dicts).

```python
# In grantflow/api/schemas.py
class AgencyResponse(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    opportunity_count: int
```

Then add `response_model=list[AgencyResponse]` to `get_agencies()`.

### Anti-Patterns to Avoid

- **Re-implementing search filter logic:** Do not write a fourth copy of the filter chain. Extract the shared helper first.
- **Unbounded bulk export:** Always apply a hard cap (e.g., 10,000 rows). Without it, a single export request can OOM the server.
- **Calling `datetime.now()` in Jinja2 templates:** Jinja2 does not have access to Python builtins by default. Pass date context from the route.
- **Registering `/opportunities/export` after `/opportunities/{id}`:** FastAPI greedy path param will swallow it. Order matters.
- **Adding pandas for CSV:** Stdlib `csv` is sufficient. Pandas adds 50MB+ to the image and is overkill.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV serialization | Custom string concatenation | `stdlib csv.writer` | Handles quoting, escaping, unicode edge cases |
| Streaming large responses | Loading all rows into memory | `StreamingResponse` with generator | Avoids OOM on large exports |
| Template date comparison | Python `datetime` calls in Jinja2 | Pass `now_date` from route context | Jinja2 has no datetime builtins by default |
| Response schema | Raw dicts from routes | Pydantic response_model | Already established pattern — agencies endpoint is the only gap |
| Rate limiting on export | Custom counter | `@limiter.limit()` decorator | slowapi already wired up |

---

## Common Pitfalls

### Pitfall 1: FastAPI Route Order — Export vs Detail
**What goes wrong:** `GET /api/v1/opportunities/export` registers after `GET /api/v1/opportunities/{opportunity_id}`. FastAPI matches "export" as an opportunity_id, returning a 404.
**Why it happens:** FastAPI evaluates routes in registration order. Literal path segments beat path parameters only when registered first.
**How to avoid:** Register the export route first in routes.py, above the `{opportunity_id}` route.
**Warning signs:** curl `GET /api/v1/opportunities/export` returns `{"detail":"Opportunity not found"}` instead of CSV.

### Pitfall 2: now_date Not in Template Context
**What goes wrong:** Closing-soon badge never shows because `now_date` evaluates to empty string (the template already has `|default('')` fallback).
**Why it happens:** The route never injects `now_date`. The stub in search.html (lines 66-68) silently does nothing.
**How to avoid:** Inject both `now_date` and `closing_soon_date` from `web/routes.py:search_page`.
**Warning signs:** Opportunities with close_date within 30 days show no badge.

### Pitfall 3: Duplicate Filter Logic Drift
**What goes wrong:** Web search and API search return different results for the same parameters because the duplicated filter code diverges.
**Why it happens:** The filter logic in `api/routes.py:search_opportunities` and `web/routes.py:search_page` is currently copy-pasted. Any fix applied to one is missed in the other.
**How to avoid:** Extract `_build_opportunity_query()` before adding the export endpoint (which would be a third copy).
**Warning signs:** Test passing for API search but not web search for same filter combo.

### Pitfall 4: CSV Content-Disposition Without Proper Quoting
**What goes wrong:** Fields containing commas or newlines (grant descriptions commonly have both) corrupt the CSV.
**Why it happens:** String formatting instead of `csv.writer`.
**How to avoid:** Always use `csv.writer` — it handles RFC 4180 quoting automatically.
**Warning signs:** Excel/Google Sheets fails to parse exported CSV; rows misaligned.

### Pitfall 5: Export Rate Limit Too Permissive
**What goes wrong:** A single API key hammers the export endpoint, exporting 10K rows repeatedly, causing DB load spikes.
**Why it happens:** Applying the same 1000/day limit as search treats export the same as a single row lookup.
**How to avoid:** Apply a stricter limit on export (e.g., `100/day`) — export is 100x more expensive per call.
**Warning signs:** DB CPU spikes correlating with API key usage.

---

## Code Examples

### Bulk Export — Verified Pattern

```python
# Source: FastAPI StreamingResponse docs + stdlib csv
import csv, io
from fastapi import Query
from fastapi.responses import StreamingResponse, JSONResponse

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
    query = _build_opportunity_query(
        db, q, status, agency, eligible, category, source,
        min_award, max_award, closing_after, closing_before
    )
    results = query.limit(10_000).all()

    if format == "json":
        return JSONResponse(content={
            "results": [OpportunityResponse.model_validate(o).model_dump() for o in results],
            "total": len(results),
        })

    COLUMNS = ["id", "title", "agency_name", "source", "opportunity_status",
               "opportunity_number", "cfda_numbers", "post_date", "close_date",
               "award_floor", "award_ceiling", "source_url"]

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(COLUMNS)
        yield buf.getvalue()
        for opp in results:
            buf.seek(0); buf.truncate(0)
            w.writerow([getattr(opp, col, None) for col in COLUMNS])
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=opportunities.csv"},
    )
```

### Stats Web Page — New Route

```python
# In web/routes.py — new /stats route
@router.get("/stats")
def stats_page(request: Request, db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    from grantflow.models import Opportunity, Award

    total = db.query(func.count(Opportunity.id)).scalar() or 0
    by_source = dict(db.query(Opportunity.source, func.count(Opportunity.id))
                       .group_by(Opportunity.source).all())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    thirty = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    closing_soon = db.query(func.count(Opportunity.id)).filter(
        Opportunity.close_date >= today,
        Opportunity.close_date <= thirty,
    ).scalar() or 0
    top_agencies = db.query(
        Opportunity.agency_name,
        func.count(Opportunity.id).label("count")
    ).group_by(Opportunity.agency_name).order_by(
        func.count(Opportunity.id).desc()
    ).limit(10).all()

    return templates.TemplateResponse(request, "stats.html", context={
        "total": total,
        "by_source": by_source,
        "closing_soon": closing_soon,
        "top_agencies": top_agencies,
    })
```

### Closing-Soon Badge in Template

```jinja2
{# In search.html — inject now_date and closing_soon_date from route context #}
{% if opp.close_date and opp.close_date >= now_date and opp.close_date <= closing_soon_date %}
<span class="badge badge-closing-soon">Closing Soon</span>
{% endif %}
```

```css
/* In static/style.css */
.badge-closing-soon {
    background: #fef3c7;
    color: #92400e;
    border: 1px solid #f59e0b;
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pandas DataFrame to CSV | `csv.writer` + `StreamingResponse` | FastAPI 0.95+ | No heavy dep; streaming prevents OOM |
| Jinja2 `{{ now() }}` custom filter | Pass date from route context | Always best practice | Keeps templates logic-free |
| `FileResponse` for downloads | `StreamingResponse` with generator | FastAPI 0.80+ | True streaming; no temp file needed |

---

## Open Questions

1. **Export row cap: 10,000 or configurable?**
   - What we know: No configuration system exists beyond env vars
   - What's unclear: Whether any API key tier should get a higher cap
   - Recommendation: Hard-code 10,000 for now; add `GRANTFLOW_EXPORT_LIMIT` env var hook for future flexibility

2. **Stats page: link from nav or separate landing?**
   - What we know: `base.html` nav has "Stats" linking to `/api/v1/stats` (JSON endpoint). Phase 7 builds the landing page.
   - What's unclear: Whether stats page should replace the JSON link or be separate
   - Recommendation: Add `/stats` web route; update nav link from `/api/v1/stats` to `/stats`

3. **Filter dedup: refactor now or later?**
   - What we know: Filter logic is duplicated in api/routes.py and web/routes.py
   - What's unclear: Whether the planner should make this refactor a required task or optional cleanup
   - Recommendation: Make it a required sub-task in the export plan (it's prerequisite — export needs a third copy otherwise)

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no version pin — installed via dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `uv run pytest tests/test_schemas.py tests/test_api_keys.py -x -q` |
| Full suite command | `uv run pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-05 | Export CSV returns 200 + Content-Disposition for valid API key | integration | `uv run pytest tests/test_export.py -x -q` | ❌ Wave 0 |
| API-05 | Export JSON returns results array | integration | `uv run pytest tests/test_export.py::test_export_json -x` | ❌ Wave 0 |
| API-05 | Export without API key returns 401 | unit | `uv run pytest tests/test_export.py::test_export_no_key -x` | ❌ Wave 0 |
| API-05 | Export respects search filters (status, agency, etc.) | integration | `uv run pytest tests/test_export.py::test_export_filters -x` | ❌ Wave 0 |
| API-06 | Detail endpoint returns `awards` list in response | integration | `uv run pytest tests/test_schemas.py::test_opportunity_detail_awards -x` | ❌ Wave 0 |
| API-08 | Agencies endpoint returns list with opportunity_count > 0 | integration | `uv run pytest tests/test_agencies.py -x -q` | ❌ Wave 0 |
| API-08 | Agencies response conforms to AgencyResponse schema | unit | `uv run pytest tests/test_agencies.py::test_agency_schema -x` | ❌ Wave 0 |
| WEB-01 | Search page renders with agency/category/eligible/date filter inputs | unit | `uv run pytest tests/test_web_ui.py::test_search_filter_inputs -x` | ❌ Wave 0 |
| WEB-02 | Detail page renders awards table when awards exist | integration | `uv run pytest tests/test_web_ui.py::test_detail_awards_section -x` | ❌ Wave 0 |
| WEB-03 | Closing-soon badge appears for opp closing within 30 days | unit | `uv run pytest tests/test_web_ui.py::test_closing_soon_badge -x` | ❌ Wave 0 |
| WEB-04 | Stats page returns 200 and contains closing_soon count | integration | `uv run pytest tests/test_web_ui.py::test_stats_page -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_export.py tests/test_agencies.py tests/test_web_ui.py -x -q`
- **Per wave merge:** `uv run pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_export.py` — covers API-05 (bulk export CSV + JSON + auth + filters)
- [ ] `tests/test_agencies.py` — covers API-08 (agencies endpoint + Pydantic schema)
- [ ] `tests/test_web_ui.py` — covers WEB-01, WEB-02, WEB-03, WEB-04 (rendered HTML checks via TestClient)

Note: `tests/test_schemas.py` exists — extend it for API-06 detail+awards rather than creating a new file.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase audit — `grantflow/api/routes.py`, `grantflow/web/routes.py`, `grantflow/api/schemas.py`, `grantflow/models.py`, `grantflow/app.py`, all templates
- FastAPI official docs (StreamingResponse, route ordering) — https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse
- Python stdlib docs (csv module) — https://docs.python.org/3/library/csv.html

### Secondary (MEDIUM confidence)
- FastAPI route ordering behavior (literal vs parameterized) — verified against FastAPI source routing behavior, consistent across 0.100+

### Tertiary (LOW confidence)
- None — all findings based on direct codebase inspection or official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — full codebase audit confirms all deps present, no new ones needed
- Architecture: HIGH — existing patterns (Pydantic schemas, limiter, templates) are established and consistent
- Pitfalls: HIGH — route ordering and template context issues verified directly from existing code (the `now_date` stub at search.html:66-68 is observable proof of Pitfall 2)

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (stable stack — 30 days)
