# Phase 11: ADA Compliance Grant Tagging & API - Context

**Gathered:** 2026-03-28
**Status:** Ready for planning
**Mode:** Auto-generated (overnight automation — yolo mode)

<domain>
## Phase Boundary

Identify and tag grants related to ADA remediation, transit accessibility, and disability compliance in the 98K-record opportunities database; expose them via GET /api/v1/opportunities/ada-compliance with optional ?municipality=<slug> filtering. No schema migrations — tag via existing topic_tags column.

</domain>

<decisions>
## Implementation Decisions

### ADA Tag Storage & Identification
- Append `"ada-compliance"` to existing `topic_tags` JSON text column — no Alembic migration needed, consistent with LLM topic tag approach
- Use a curated keyword list matching on title + description + agency_name fields — deterministic, fast, no API cost
- Backfill all 98K existing records once via a startup/CLI script
- Single `"ada-compliance"` tag — simple to filter, consistent with existing topic_tags filtering in build_opportunity_query()

### ADA Keyword List (curated)
Key terms to match across title/description/agency_name (case-insensitive):
- "ADA", "Americans with Disabilities Act", "disability access", "accessibility compliance"
- "transit accessibility", "accessible transit", "paratransit", "ADA transition plan"
- "wheelchair", "curb cut", "pedestrian accessibility", "sidewalk accessibility"
- "Section 504", "rehabilitation act", "disability remediation", "accessible facilities"
- "All Stations Access", "station accessibility", "rail accessibility", "bus accessibility"
- "FTA accessibility", "accessible transportation", "disability infrastructure"
- Agency matches: "FTA", "Federal Transit Administration", "Office of Special Education"

### API Design
- No API key required — this is a public resource endpoint for municipality buyers discovering grants (fail open, maximize utility)
- Apply rate limiting via existing limiter (same as other endpoints) for DoS protection even without key
- Reuse OpportunityResponse schema — DRY, consistent contract
- Default sort: close_date ASC NULLS LAST (deadline proximity — most urgent grants first)
- Support standard pagination: ?page=&per_page= (default 20, max 100)
- Support ?municipality=<slug> optional filter

### Municipality Cross-Link
- Accept any municipality slug as a free-text param — no predefined mapping table (YAGNI)
- Matching strategy: keyword match municipality slug against eligible_applicants + description fields (ilike)
- Fallback: if municipality slug matches nothing, return all ADA compliance grants (fail open)
- No ?violation_type= param — out of scope for this phase

### Claude's Discretion
- ADA keyword backfill script location: grantflow/pipeline/ada_tagger.py (CLI callable via `uv run python -m grantflow.pipeline.ada_tagger`)
- Whether to run backfill at app startup or as a separate CLI step — prefer CLI to avoid startup time impact
- Error handling for malformed topic_tags JSON — handle gracefully

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `build_opportunity_query()` in grantflow/api/query.py — extend or reuse for ADA filtering
- `topic_tags` column on Opportunity model — existing Text column storing JSON string, already used for LLM tags
- `OpportunityResponse` + `SearchResponse` Pydantic schemas in grantflow/api/schemas.py — reuse directly
- `_tier_limit` from grantflow/api/auth.py — reuse for rate limiting
- `limiter` from grantflow/app.py — import for @limiter.limit decorator
- `get_db` from grantflow/database.py — standard DB dependency

### Established Patterns
- API routes: `@router.get(path, response_model=..., tags=[...])` + `@limiter.limit(_tier_limit)` with `request: Request` first param
- No-auth endpoint: see `/api/v1/health` — no `api_key: ApiKey = Depends(get_api_key)` dependency
- topic_tags filter in query.py: `query.filter(Opportunity.topic_tags.ilike(f'%"{topic}"%'))` — same pattern for ada-compliance
- Sort pattern: `.order_by(Opportunity.close_date.asc().nullslast())`

### Integration Points
- New route registers in `grantflow/api/routes.py` on existing `router = APIRouter(prefix="/api/v1")`
- App entry: `grantflow/app.py` includes router — no changes needed there
- Backfill script: standalone CLI in `grantflow/pipeline/ada_tagger.py`

</code_context>

<specifics>
## Specific Ideas

- User context: DOT FTA "All Stations Access" grant (deadline 2026-05-01) MUST appear in results — "All Stations Access" and "FTA" should be in keyword list
- Endpoint path: `/api/v1/opportunities/ada-compliance` (exact, as specified)
- Municipality param: `?municipality=<slug>` — slug is free text (e.g., "boston-ma", "chicago-il")
- The route must be registered BEFORE `/{opportunity_id}` path param route to avoid FastAPI path resolution conflicts (established pattern from Phase 6)

</specifics>

<deferred>
## Deferred Ideas

- Granular sub-tags (ada-remediation, transit-accessibility, disability-compliance) — single tag sufficient for v1
- ?violation_type= query param — out of scope, Phase 12 can add if needed
- Pre-built municipality→violation_type mapping table — YAGNI until ada-audit integration is specified
- Scheduled re-tagging as new records ingest — can be added when ada_tagger is stable

</deferred>
