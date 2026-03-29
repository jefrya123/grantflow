# Phase 11: ADA Compliance Grant Tagging & API - Research

**Researched:** 2026-03-28
**Domain:** FastAPI route extension + SQLAlchemy text-column tagging + keyword backfill script
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**ADA Tag Storage & Identification**
- Append `"ada-compliance"` to existing `topic_tags` JSON text column — no Alembic migration needed, consistent with LLM topic tag approach
- Use a curated keyword list matching on title + description + agency_name fields — deterministic, fast, no API cost
- Backfill all 98K existing records once via a startup/CLI script
- Single `"ada-compliance"` tag — simple to filter, consistent with existing topic_tags filtering in build_opportunity_query()

**ADA Keyword List (curated)**
Key terms to match across title/description/agency_name (case-insensitive):
- "ADA", "Americans with Disabilities Act", "disability access", "accessibility compliance"
- "transit accessibility", "accessible transit", "paratransit", "ADA transition plan"
- "wheelchair", "curb cut", "pedestrian accessibility", "sidewalk accessibility"
- "Section 504", "rehabilitation act", "disability remediation", "accessible facilities"
- "All Stations Access", "station accessibility", "rail accessibility", "bus accessibility"
- "FTA accessibility", "accessible transportation", "disability infrastructure"
- Agency matches: "FTA", "Federal Transit Administration", "Office of Special Education"

**API Design**
- No API key required — public resource endpoint (fail open, maximize utility)
- Apply rate limiting via existing limiter for DoS protection even without key
- Reuse OpportunityResponse schema — DRY, consistent contract
- Default sort: close_date ASC NULLS LAST (deadline proximity — most urgent first)
- Support standard pagination: ?page=&per_page= (default 20, max 100)
- Support ?municipality=<slug> optional filter

**Municipality Cross-Link**
- Accept any municipality slug as a free-text param — no predefined mapping table (YAGNI)
- Matching strategy: keyword match municipality slug against eligible_applicants + description fields (ilike)
- Fallback: if municipality slug matches nothing, return all ADA compliance grants (fail open)
- No ?violation_type= param — out of scope for this phase

**Claude's Discretion**
- ADA keyword backfill script location: grantflow/pipeline/ada_tagger.py (CLI callable via `uv run python -m grantflow.pipeline.ada_tagger`)
- Whether to run backfill at app startup or as a separate CLI step — prefer CLI to avoid startup time impact
- Error handling for malformed topic_tags JSON — handle gracefully

### Deferred Ideas (OUT OF SCOPE)
- Granular sub-tags (ada-remediation, transit-accessibility, disability-compliance) — single tag sufficient for v1
- ?violation_type= query param — out of scope, Phase 12 can add if needed
- Pre-built municipality→violation_type mapping table — YAGNI until ada-audit integration is specified
- Scheduled re-tagging as new records ingest — can be added when ada_tagger is stable
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ADA-01 | `ada_tags` JSON column (or equivalent) populated for all grants matching ADA/accessibility keyword criteria across title, description, and agency fields | Use existing `topic_tags` Text column — append `"ada-compliance"` string. Backfill script iterates all 98,949 records using raw SQL UPDATE to avoid ORM/search_vector collision. ~302 records will match precise keyword set. |
| ADA-02 | GET /api/v1/opportunities/ada-compliance returns paginated results with title, deadline, award_min, award_max, source, apply_url, and canonical_id | Reuse `OpportunityResponse` + `SearchResponse` schemas (already include all required fields). Register route BEFORE `/{opportunity_id}` in routes.py. No auth dependency — omit `api_key: ApiKey = Depends(get_api_key)`. |
| ADA-03 | Endpoint accepts optional `?municipality=<slug>` and returns grants relevant to that municipality's violation type profile; documented in OpenAPI; 200/422 responses | Use ilike match of slug against `eligible_applicants` + `description` fields. FastAPI auto-generates 422 for invalid params. OpenAPI docs covered by `response_model=SearchResponse, tags=["ada-compliance"]`. |
</phase_requirements>

---

## Summary

Phase 11 is a focused extension to an already-complete FastAPI + PostgreSQL stack. It involves two deliverables: (1) a backfill CLI script that appends `"ada-compliance"` to the existing `topic_tags` JSON text column for matching records, and (2) a new no-auth API endpoint at `/api/v1/opportunities/ada-compliance` that filters on that tag with optional municipality slug filtering.

The existing codebase has everything needed. The `topic_tags` column is a Text column storing a JSON array string (e.g., `'["health", "research"]'`). The LLM tagger writes to it; the ada_tagger will append to it using the same ilike-on-JSON-string pattern. No schema migration is required. The `build_opportunity_query()` function already filters by topic tag using `ilike(f'%"{topic}"%')` — the ADA endpoint can either reuse that function or inline an equivalent filter.

The critical data finding: raw `'ADA'` substring matching generates ~5,051 false positives (adaptation, Adams, etc.). The curated keyword list from CONTEXT.md — which avoids bare `'ADA'` in favor of contextually qualified terms and uses `agency_name` matching for FTA — produces approximately 302 clean matches. The FY 2026 "All Stations Accessibility Program" grant (deadline 2026-05-01, source `grants_gov`, agency `DOT/Federal Transit Administration`) IS present in the database and will be captured by the FTA agency_name match.

**Primary recommendation:** Two-plan structure — Plan A: `ada_tagger.py` CLI backfill script + unit tests; Plan B: `/api/v1/opportunities/ada-compliance` route + integration tests.

---

## Standard Stack

### Core (all already installed — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | existing | Route definition, OpenAPI generation | Already in stack |
| SQLAlchemy | existing | ORM query + raw SQL for backfill | Already in stack |
| Pydantic v2 | existing | Response schema validation | Already in stack |
| slowapi | existing | Rate limiting on new route | Already in stack |
| pytest | existing | Test suite | Already in stack |

**No new packages required.** This phase is pure code extension.

---

## Architecture Patterns

### Recommended File Structure

```
grantflow/
├── pipeline/
│   └── ada_tagger.py         # NEW: backfill CLI script
├── api/
│   └── routes.py             # MODIFIED: add ada-compliance route (before /{id})
tests/
└── test_ada_compliance.py    # NEW: unit + integration tests
```

### Pattern 1: No-Auth Endpoint Registration Order

The export route is already registered before `/{opportunity_id}` to prevent FastAPI path resolution conflict (Phase 6 decision). The ada-compliance route must follow the same pattern:

```python
# routes.py — CORRECT ORDER
@router.get("/opportunities/search", ...)        # line ~29 — static segment
@router.get("/opportunities/export", ...)        # line ~116 — static segment
@router.get("/opportunities/ada-compliance", ...) # NEW — static segment, BEFORE /{id}
@router.get("/opportunities/{opportunity_id}", ...) # line ~182 — path param — MUST BE LAST
```

Any static path under `/opportunities/` placed AFTER `/{opportunity_id}` will be shadowed — FastAPI will route `ada-compliance` as the value of `opportunity_id`.

### Pattern 2: No-Auth Route Signature

The `/health` endpoint demonstrates the no-auth pattern. For the ada-compliance route, omit `api_key: ApiKey = Depends(get_api_key)` but keep `request: Request` as first param (required by `@limiter.limit`):

```python
@router.get(
    "/opportunities/ada-compliance",
    response_model=SearchResponse,
    tags=["ada-compliance"],
    summary="ADA compliance and accessibility grants",
)
@limiter.limit(_tier_limit)
def get_ada_compliance_grants(
    request: Request,
    municipality: str | None = Query(default=None, description="Municipality slug (e.g. 'boston-ma')"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    # NO api_key dependency — public endpoint
) -> SearchResponse:
    ...
```

Note: `_tier_limit` keys on `X-API-Key` header with fallback to IP address (see `app.py` limiter definition). For unauthenticated callers, rate limiting applies per IP. This is correct behavior.

### Pattern 3: topic_tags Filter (exact match on JSON string)

The existing filter in `query.py` line 74:
```python
query = query.filter(Opportunity.topic_tags.ilike(f'%"{topic}"%'))
```

This searches for `"ada-compliance"` (with quotes) within the JSON string, preventing false matches on substrings. The backfill must write `"ada-compliance"` as a quoted JSON array element for this filter to work.

### Pattern 4: ADA Backfill Script (raw SQL, not ORM)

The Phase 4 and Phase 10 precedents (`assign_canonical_ids`, `BaseStateScraper.run()`, backfill scripts) all use raw SQL to avoid the ORM loading `search_vector` (TSVECTORType that doesn't exist in SQLite test schema):

```python
# ada_tagger.py — use raw SQL SELECT + UPDATE pattern
from sqlalchemy import text

def _is_ada_match(row) -> bool:
    """Return True if row matches any ADA keyword criteria."""
    title = (row.title or "").lower()
    desc = (row.description or "").lower()
    agency = (row.agency_name or "").lower()
    # Check precise keyword list — no bare 'ada' to avoid false positives
    ...

def run_ada_backfill(db):
    result = db.execute(text(
        "SELECT id, title, description, agency_name, topic_tags FROM opportunities"
    ))
    updated = 0
    for row in result:
        if _is_ada_match(row):
            existing = _parse_tags(row.topic_tags)
            if "ada-compliance" not in existing:
                existing.append("ada-compliance")
                db.execute(
                    text("UPDATE opportunities SET topic_tags = :tags WHERE id = :id"),
                    {"tags": json.dumps(existing), "id": row.id}
                )
                updated += 1
    db.commit()
    return updated
```

### Pattern 5: topic_tags JSON Handling (malformed input guard)

The topic_tags column is `None` for all 98,949 current records (LLM enrichment has not run yet — `total topic_tags non-null: 0`). The backfill must handle three cases:
1. `None` → start fresh: `["ada-compliance"]`
2. Valid JSON array string → parse, append if not present, re-serialize
3. Malformed JSON string → treat as empty list, log warning, write `["ada-compliance"]`

```python
def _parse_tags(raw: str | None) -> list[str]:
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []  # malformed — start clean
```

### Pattern 6: Municipality Slug Matching

`eligible_applicants` stores values like `'["City or township governments"]'` — generic categories, not city names. No city names appear in `eligible_applicants` (confirmed: 0 records). The municipality slug match must target `description` and `eligible_applicants` with ilike on the slug string:

```python
if municipality:
    slug_term = f"%{municipality}%"
    # eligible_applicants contains generic categories — slug rarely matches here
    # description sometimes contains city names (10 records found with specific city names)
    # Both fields searched; fallback: return all ADA grants if nothing matches
    muni_query = ada_query.filter(
        or_(
            Opportunity.eligible_applicants.ilike(slug_term),
            Opportunity.description.ilike(slug_term),
        )
    )
    if muni_query.count() > 0:
        ada_query = muni_query
    # else: fall through and return all ADA grants (fail-open)
```

**Key finding:** Municipality slug matching against this dataset will almost never produce city-specific results because `eligible_applicants` uses generic categories and `description` rarely contains city names. The fail-open behavior (return all ADA grants) is correct and matches the CONTEXT.md decision. This is not a bug — it is the specified behavior.

### Anti-Patterns to Avoid

- **Bare 'ADA' substring match in backfill:** 5,051 false positives — `ADA` appears in "adaptation", "Adams", "NADAC", etc. The keyword list must use contextually qualified terms (e.g., `"Americans with Disabilities Act"`, `"ADA compliance"`, `"ADA transition"`).
- **Using ORM query in backfill script:** Will crash on SQLite test DB due to `TSVECTORType` on `search_vector` column. Use raw SQL `SELECT` (established Phase 4/10 pattern).
- **Placing ada-compliance route after `/{opportunity_id}`:** FastAPI will treat `ada-compliance` as a path param value — established Phase 6 pattern.
- **Committing inside the per-row loop:** Commit once after all updates — avoids transaction overhead on 98K rows.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Response schema | Custom dict serializer | `OpportunityResponse` + `SearchResponse` | Already has all required fields; DRY |
| Rate limiting | Custom middleware | `@limiter.limit(_tier_limit)` | Already wired; keys on X-API-Key or IP |
| Pagination math | Custom offset/limit | Reuse search_opportunities pattern | `pages = max(1, (total + per_page - 1) // per_page)` — already correct |
| JSON tag detection | Custom contains logic | `ilike(f'%"ada-compliance"%')` | Existing pattern from query.py; handles JSON quoting |
| Test DB setup | New fixture | Existing `conftest.py` fixtures (`client`, `db_session`) | Session-scoped engine, function-scoped rollback |

---

## Common Pitfalls

### Pitfall 1: False Positives from Bare 'ADA' Match
**What goes wrong:** Bare `ilike('%ADA%')` matches 5,051 records — most are "adaptation", "Adams County", "NADAC", "PADA". Only ~302 records are genuine ADA-disability matches.
**Why it happens:** "ADA" is a common abbreviation and substring in English text.
**How to avoid:** Use contextually qualified terms only: `"Americans with Disabilities Act"`, `"ADA compliance"`, `"ADA transition plan"`, `"ADA access"`, `"ADA standards"`. Never match bare `"ADA"` or `"%ADA%"`.
**Warning signs:** Backfill reports tagging >1,000 records — likely caught a false-positive batch.

### Pitfall 2: Route Registration Order
**What goes wrong:** Adding the ada-compliance route after `/{opportunity_id}` causes FastAPI to route `/opportunities/ada-compliance` as `opportunity_id="ada-compliance"`, returning 404.
**Why it happens:** FastAPI resolves routes in registration order — path params shadow static segments.
**How to avoid:** Insert the new route before `@router.get("/opportunities/{opportunity_id}", ...)` in routes.py. Current order: search (line 29), export (line 116), `/{id}` (line 182). Insert at ~line 117.
**Warning signs:** GET /api/v1/opportunities/ada-compliance returns 404 "Opportunity not found".

### Pitfall 3: ORM Query in Backfill Crashes on SQLite
**What goes wrong:** `db.query(Opportunity)` in the backfill script crashes in test environment because `TSVECTORType` on `search_vector` doesn't resolve cleanly in SQLite.
**Why it happens:** ORM loads all columns including `search_vector`; the TSVECTORType TypeDecorator behaves differently under SQLite.
**How to avoid:** Use `db.execute(text("SELECT id, title, description, agency_name, topic_tags FROM opportunities"))` — explicit raw SQL selects only needed columns. This is the established project pattern (Phase 4, Phase 10).
**Warning signs:** `OperationalError: no such column: search_vector` in tests.

### Pitfall 4: topic_tags Format Mismatch
**What goes wrong:** Backfill writes `'ada-compliance'` (unquoted) instead of `'["ada-compliance"]'` (JSON array). The existing filter `ilike('%"ada-compliance"%')` requires the value to be a quoted JSON string element.
**Why it happens:** Inconsistency between how tags are stored vs. how they're queried.
**How to avoid:** Always serialize with `json.dumps(["ada-compliance"])` → `'["ada-compliance"]'`. The ilike filter specifically looks for `"ada-compliance"` with surrounding quotes.
**Warning signs:** Backfill reports N records updated, but endpoint returns 0 results.

### Pitfall 5: Municipality Slug Never Matches — Unexpected Empty Response
**What goes wrong:** Municipality slug filtered query returns 0 results, breaking the expected fail-open behavior if the fallback isn't implemented.
**Why it happens:** `eligible_applicants` contains only generic category strings ("City or township governments", "Unrestricted") — never city names. Description occasionally contains city names but rarely for accessibility grants.
**How to avoid:** Always check count > 0 before applying municipality filter; fall through to return all ADA grants when slug matches nothing. This is specified in CONTEXT.md.
**Warning signs:** `?municipality=boston-ma` returns empty results instead of all ADA grants.

---

## Code Examples

### ADA Backfill Script Skeleton

```python
# grantflow/pipeline/ada_tagger.py
# Source: Project pattern from grantflow/ingest/run_all.py + assign_canonical_ids

import json
import logging
from sqlalchemy import text
from grantflow.database import SessionLocal

logger = logging.getLogger(__name__)

# Precise keyword list — NO bare 'ADA' to avoid false positives
ADA_TITLE_KEYWORDS = [
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
]

ADA_DESC_KEYWORDS = [
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
]

ADA_AGENCY_KEYWORDS = [
    "federal transit administration",
]


def _is_ada_match(title: str, description: str, agency_name: str) -> bool:
    t = (title or "").lower()
    d = (description or "").lower()
    a = (agency_name or "").lower()
    return (
        any(kw in t for kw in ADA_TITLE_KEYWORDS)
        or any(kw in d for kw in ADA_DESC_KEYWORDS)
        or any(kw in a for kw in ADA_AGENCY_KEYWORDS)
    )


def _parse_tags(raw: str | None) -> list[str]:
    if raw is None:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def run_ada_backfill(db=None) -> int:
    """Tag all ADA-matching opportunities. Returns count of records updated."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        rows = db.execute(
            text("SELECT id, title, description, agency_name, topic_tags FROM opportunities")
        )
        updated = 0
        for row in rows:
            if _is_ada_match(row.title, row.description, row.agency_name):
                tags = _parse_tags(row.topic_tags)
                if "ada-compliance" not in tags:
                    tags.append("ada-compliance")
                    db.execute(
                        text("UPDATE opportunities SET topic_tags = :tags WHERE id = :id"),
                        {"tags": json.dumps(tags), "id": row.id},
                    )
                    updated += 1
        db.commit()
        logger.info("ADA backfill complete", extra={"updated": updated})
        return updated
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    count = run_ada_backfill()
    print(f"Tagged {count} records as ada-compliance")
```

### ADA Endpoint Skeleton

```python
# grantflow/api/routes.py — insert BEFORE /{opportunity_id} route

@router.get(
    "/opportunities/ada-compliance",
    response_model=SearchResponse,
    tags=["ada-compliance"],
    summary="ADA compliance and accessibility grants",
    description="Returns paginated ADA/accessibility grants sorted by deadline. No API key required.",
)
@limiter.limit(_tier_limit)
def get_ada_compliance_grants(
    request: Request,
    municipality: str | None = Query(
        default=None,
        description="Optional municipality slug (e.g. 'boston-ma'). Falls back to all ADA grants if no match.",
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    # Base: all ada-compliance tagged grants
    ada_query = db.query(Opportunity).filter(
        Opportunity.topic_tags.ilike('%"ada-compliance"%')
    )

    # Municipality filter — fail open
    if municipality:
        slug_term = f"%{municipality}%"
        muni_query = ada_query.filter(
            or_(
                Opportunity.eligible_applicants.ilike(slug_term),
                Opportunity.description.ilike(slug_term),
            )
        )
        if muni_query.count() > 0:
            ada_query = muni_query
        # else: fall through — return all ADA grants

    # Sort by deadline proximity
    ada_query = ada_query.order_by(Opportunity.close_date.asc().nullslast())

    total = ada_query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page
    results = ada_query.offset(offset).limit(per_page).all()

    return SearchResponse(
        results=[OpportunityResponse.model_validate(o) for o in results],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )
```

---

## State of the Art

| Old Approach | Current Approach | Impact for This Phase |
|--------------|------------------|----------------------|
| LLM-only tagging | Deterministic keyword backfill | No API cost, no rate limits, 100% reproducible |
| ORM query in scripts | Raw SQL SELECT (Phase 4/10 pattern) | Required to avoid TSVECTORType crash in SQLite tests |
| topic_tags absent | topic_tags=None for all 98,949 records | Backfill starts from a clean slate — no merge conflicts |

---

## Open Questions

1. **Keyword list completeness for `"Office of Special Education"`**
   - What we know: CONTEXT.md includes this as an agency match, but database probe shows 0 FTA records with that agency name. Special Education grants may not be accessibility-relevant.
   - What's unclear: Whether OSEP (Office of Special Education Programs) grants should be in ADA compliance scope.
   - Recommendation: Omit bare "Office of Special Education" from the agency match list — it would tag IDEA/education grants that are not infrastructure ADA compliance. Keep FTA only.

2. **"Section 504" generates 45 title matches — are they all relevant?**
   - What we know: Section 504 of the Rehabilitation Act covers disability access broadly, not just transit. Some matches may be education/employment focused.
   - What's unclear: Whether to restrict Section 504 to description-only (more context-specific) or also title.
   - Recommendation: Use Section 504 in description match only — description provides enough context to disambiguate transit/facility accessibility from employment/education.

3. **FY 2026 ASAP grant has `eligible_applicants='["Others (see agency eligibility text)"]'`**
   - What we know: Municipality slug match against this record will never match on eligible_applicants.
   - What's unclear: Nothing — this is expected; the fail-open behavior returns the grant in all ADA queries regardless.
   - Recommendation: No action needed; the grant appears in base ADA results and success criterion is met.

---

## Environment Availability

Step 2.6: SKIPPED (no external dependencies — pure Python code/SQL, no new services or CLIs required beyond existing stack).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | none — pytest finds tests/ by convention |
| Quick run command | `uv run pytest tests/test_ada_compliance.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADA-01 | `_is_ada_match()` returns True for ADA keywords, False for false positives | unit | `uv run pytest tests/test_ada_compliance.py::test_keyword_matching -x` | Wave 0 |
| ADA-01 | `run_ada_backfill()` tags matching records, skips non-matching | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_tags_matching_records -x` | Wave 0 |
| ADA-01 | `run_ada_backfill()` handles malformed topic_tags without crashing | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_malformed_tags -x` | Wave 0 |
| ADA-01 | `run_ada_backfill()` is idempotent (re-running does not duplicate tag) | unit | `uv run pytest tests/test_ada_compliance.py::test_backfill_idempotent -x` | Wave 0 |
| ADA-02 | GET /api/v1/opportunities/ada-compliance returns 200 + SearchResponse | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_returns_200 -x` | Wave 0 |
| ADA-02 | Endpoint returns correct fields (title, close_date, award_floor, award_ceiling, source, source_url, canonical_id) | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_response_fields -x` | Wave 0 |
| ADA-02 | Results sorted by close_date ASC nullslast | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_sort_order -x` | Wave 0 |
| ADA-02 | Pagination works (page/per_page params) | integration | `uv run pytest tests/test_ada_compliance.py::test_endpoint_pagination -x` | Wave 0 |
| ADA-03 | ?municipality=<slug> filters by ilike on eligible_applicants+description | integration | `uv run pytest tests/test_ada_compliance.py::test_municipality_filter -x` | Wave 0 |
| ADA-03 | ?municipality=<slug> with no match returns all ADA grants (fail-open) | integration | `uv run pytest tests/test_ada_compliance.py::test_municipality_fallback -x` | Wave 0 |
| ADA-03 | Invalid per_page (>100) returns 422 | integration | `uv run pytest tests/test_ada_compliance.py::test_invalid_param_422 -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_ada_compliance.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ada_compliance.py` — covers all ADA-01, ADA-02, ADA-03 requirements (does not exist yet)

---

## Project Constraints (from CLAUDE.md — global)

| Directive | Impact on This Phase |
|-----------|---------------------|
| Python CLI tools: prefix with `uv run` | Backfill script invoked as `uv run python -m grantflow.pipeline.ada_tagger` |
| TDD: write failing test first, then implement | Write `test_ada_compliance.py` before `ada_tagger.py` and route |
| Never hardcode secrets/API keys | No secrets involved — endpoint is public, no LLM calls |
| Post-task: run formatter, linter, type checker | Run `uv run ruff check` + `uv run mypy` if configured after implementation |
| Auth/API boundaries: apply OWASP guidelines | Endpoint is intentionally public — confirm no sensitive data exposure in responses |
| YAGNI — no speculative features | No violation_type param, no sub-tags, no municipality mapping table |

---

## Sources

### Primary (HIGH confidence)
- Direct database probe via SQLAlchemy — actual record counts, field formats, keyword hit rates
- `/home/jeff/Projects/grantflow/grantflow/api/routes.py` — route registration order, no-auth pattern, response models
- `/home/jeff/Projects/grantflow/grantflow/api/query.py` — `build_opportunity_query()` and topic_tags ilike pattern
- `/home/jeff/Projects/grantflow/grantflow/api/schemas.py` — OpportunityResponse fields (title, close_date, award_floor, award_ceiling, source, source_url, canonical_id all present)
- `/home/jeff/Projects/grantflow/grantflow/api/auth.py` — `_tier_limit` callable, `get_api_key` dependency signature
- `/home/jeff/Projects/grantflow/grantflow/app.py` — limiter definition (keys on X-API-Key || IP)
- `/home/jeff/Projects/grantflow/grantflow/models.py` — topic_tags is `Column(Text, nullable=True)` with no schema constraint
- `/home/jeff/Projects/grantflow/.planning/STATE.md` — accumulated project decisions (raw SQL for scripts, route order pattern)

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions (user-locked) — ADA keyword list, API design choices, municipality strategy

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries already in use
- Architecture patterns: HIGH — derived from reading actual source files and running DB probes
- Pitfalls: HIGH — false-positive count (5,051 vs 302) confirmed by live DB query; route order issue confirmed from Phase 6 STATE.md decision
- Keyword effectiveness: MEDIUM — 302 records confirmed as matching the curated list; completeness of keyword list not exhaustively verified against all 98K records

**Research date:** 2026-03-28
**Valid until:** 2026-04-28 (stable codebase; no fast-moving dependencies)
