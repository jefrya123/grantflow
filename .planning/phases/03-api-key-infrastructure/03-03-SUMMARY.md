---
phase: 03-api-key-infrastructure
plan: "03"
subsystem: api
tags: [pydantic, fastapi, openapi, response-models, schema-contract]

requires:
  - phase: 03-api-key-infrastructure-01
    provides: keys.py route with POST /api/v1/keys
  - phase: 01-foundation
    provides: SQLAlchemy Opportunity and Award ORM models

provides:
  - Pydantic v2 response schemas for all API endpoints (schemas.py)
  - Stable field-name contract enforced via response_model= on all data routes
  - Accurate OpenAPI docs at /docs (fully typed, no untyped dicts on data endpoints)
  - Schema contract test suite (13 tests)

affects:
  - 04-search-api
  - 05-billing-and-rate-limiting
  - 06-agency-profiles

tech-stack:
  added: []
  patterns:
    - "Pydantic v2 ConfigDict(from_attributes=True) on all ORM-backed response models"
    - "response_model= on every data route decorator for automatic serialization and OpenAPI generation"
    - "OpportunityDetailResponse extends OpportunityResponse — inheritance for detail vs list shapes"

key-files:
  created:
    - grantflow/api/schemas.py
    - tests/test_schemas.py
  modified:
    - grantflow/api/routes.py
    - grantflow/api/keys.py
    - grantflow/app.py

key-decisions:
  - "eligible_applicants kept as Optional[str] — stored as JSON string in Text column, parsing out of scope"
  - "agencies endpoint left without response_model — Phase 6 scope, returns list[dict] (plan spec)"
  - "health endpoint left without response_model — dynamic structure, not a data contract endpoint"
  - "KeyCreateResponse returns Pydantic object directly from keys.py route (not dict)"

patterns-established:
  - "All ORM-backed models use ConfigDict(from_attributes=True) — enables .model_validate(orm_obj) directly"
  - "Detail response (with nested list) is a subclass of list response — no field duplication"

requirements-completed: [API-03, API-07]

duration: 2min
completed: 2026-03-24
---

# Phase 03 Plan 03: Pydantic Response Schemas Summary

**Replaced hand-rolled _opportunity_to_dict() serializer with Pydantic v2 response models wired as response_model= on all data routes, locking the API field-name contract and generating accurate OpenAPI docs**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T18:26:23Z
- **Completed:** 2026-03-24T18:28:56Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `grantflow/api/schemas.py` with 6 Pydantic v2 models: OpportunityResponse, AwardResponse, OpportunityDetailResponse, SearchResponse, KeyCreateResponse, StatsResponse
- Deleted `_opportunity_to_dict()` and `_award_to_dict()` helper functions; replaced with `.model_validate()` calls on all routes
- Added `response_model=` to GET /opportunities/search, GET /opportunities/{id}, GET /stats, POST /keys
- Updated FastAPI app with version="1.0.0", explicit docs_url/redoc_url, and openapi_tags description
- 13 schema contract tests passing; full suite 57/57 green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Pydantic response schemas** - `b550960` (feat + test — TDD)
2. **Task 2: Wire response_model= to all routes and update OpenAPI metadata** - `7dbabc1` (feat)

**Plan metadata:** _(docs commit — see below)_

_Note: Task 1 used TDD — tests written first (RED), then schemas implemented (GREEN)._

## Files Created/Modified

- `grantflow/api/schemas.py` — Pydantic v2 response models for all endpoints
- `tests/test_schemas.py` — 13 schema contract tests (field presence, types, ORM compatibility)
- `grantflow/api/routes.py` — Replaced dict serializers with model_validate(); added response_model= and tags
- `grantflow/api/keys.py` — Added response_model=KeyCreateResponse; returns KeyCreateResponse object
- `grantflow/app.py` — Added version, docs_url, redoc_url, openapi_tags

## Decisions Made

- `eligible_applicants` kept as `Optional[str]` — it's stored as a raw JSON string in the Text column; parsing to a list is out of scope for this plan per spec
- The agencies endpoint (`GET /agencies`) was left without a response_model — it returns a simple list of dicts and the plan spec explicitly deferred this to Phase 6
- The health endpoint (`GET /health`) was left without a response_model — it has dynamic structure with nested source dicts, not a data contract endpoint
- `KeyCreateResponse` is now returned as a Pydantic object from `create_api_key()` (not a raw dict) to be consistent with the response_model contract

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All 57 tests passed on first run after implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- API schema contract is stable and enforced via Pydantic — field names cannot accidentally drift
- OpenAPI docs at /docs are accurate and fully typed for all data endpoints
- All existing tests pass with no regressions
- Ready for Phase 4 (search API enhancements) and Phase 5 (billing/rate limiting) which can rely on the stable response contracts

---
*Phase: 03-api-key-infrastructure*
*Completed: 2026-03-24*
