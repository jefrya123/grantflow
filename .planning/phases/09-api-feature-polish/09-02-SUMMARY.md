---
phase: 09-api-feature-polish
plan: "02"
subsystem: api
tags: [pydantic, apscheduler, openai, enrichment, schema]

requires:
  - phase: 07-gtm-enrichment
    provides: run_enrichment() CLI function with OPENAI_API_KEY gate
  - phase: 04-data-quality
    provides: canonical_id column on Opportunity ORM model

provides:
  - canonical_id field exposed in OpportunityResponse and OpportunityDetailResponse API schemas
  - daily_enrichment APScheduler job wired at 04:00 UTC using run_in_executor pattern

affects:
  - any future plan that extends OpportunityResponse schema (will see canonical_id)
  - any plan that inspects scheduler job list (daily_enrichment now registered)

tech-stack:
  added: []
  patterns:
    - run_in_executor wrapping for sync functions called from APScheduler in async context
    - Pydantic from_attributes=True ORM mapping picks up new column without additional wiring

key-files:
  created: []
  modified:
    - grantflow/api/schemas.py
    - grantflow/app.py
    - tests/test_schemas.py
    - tests/test_enrichment.py

key-decisions:
  - "canonical_id added to OpportunityResponse after topic_tags — OpportunityDetailResponse inherits automatically via subclass"
  - "daily_enrichment job registered unconditionally — OPENAI_API_KEY gate lives inside run_enrichment(), not at scheduler level"
  - "run_in_executor wrapping on run_enrichment() mirrors existing daily_ingestion pattern — prevents RuntimeError from nested asyncio.run()"

patterns-established:
  - "Scheduler job registration pattern: add_job with CronTrigger + run_in_executor + replace_existing=True + misfire_grace_time=3600"
  - "Scheduler test pattern: use client fixture (triggers lifespan), inspect scheduler.get_jobs() from grantflow.app"

requirements-completed: [QUAL-03, QUAL-04]

duration: 2min
completed: 2026-03-24
---

# Phase 09 Plan 02: API Feature Polish — canonical_id and Enrichment Scheduler Summary

**canonical_id exposed in all opportunity API responses and LLM enrichment wired into APScheduler at 04:00 UTC via run_in_executor**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-24T17:19:44Z
- **Completed:** 2026-03-24T17:21:59Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `canonical_id: Optional[str] = None` to `OpportunityResponse`; `OpportunityDetailResponse` inherits it automatically
- Registered `daily_enrichment` APScheduler job at 04:00 UTC using the `run_in_executor` pattern matching existing scheduler jobs
- Updated schema contract test (`test_opportunity_response_preserves_exact_field_names`) and added integration test (`test_canonical_id_in_api_response`)
- Added scheduler registration tests (`test_enrichment_scheduler_job_registered`, `test_enrichment_job_runs_at_0400_utc`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Expose canonical_id in OpportunityResponse schema** - `6b70d60` (feat)
2. **Task 2: Wire LLM enrichment into APScheduler daily schedule** - `45caf28` (feat)

**Plan metadata:** (docs commit follows)

_Note: Both tasks used TDD (RED then GREEN)_

## Files Created/Modified

- `grantflow/api/schemas.py` — Added `canonical_id: Optional[str] = None` to `OpportunityResponse`
- `grantflow/app.py` — Imported `run_enrichment`, added `daily_enrichment` scheduler job at 04:00 UTC
- `tests/test_schemas.py` — Added `"canonical_id"` to expected_keys set; added `test_canonical_id_in_api_response`
- `tests/test_enrichment.py` — Added `test_enrichment_scheduler_job_registered` and `test_enrichment_job_runs_at_0400_utc`

## Decisions Made

- `canonical_id` placed after `topic_tags` in `OpportunityResponse` to follow existing field ordering convention
- OPENAI_API_KEY gate stays inside `run_enrichment()` — scheduler registers the job unconditionally (silent no-op when key absent)
- `run_in_executor` wrapping is mandatory because `run_enrichment()` calls `asyncio.run()` internally, which raises `RuntimeError` if called inside a running event loop

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing failure in `tests/test_auth_ratelimit.py::test_tier_limit_starter` (rate limit tier mismatch `1000/day` vs `10000/day`) confirmed to be unrelated to this plan. Logged for deferred attention.

## Next Phase Readiness

- Phase 09 complete — all API feature polish requirements (QUAL-03, QUAL-04) fulfilled
- `canonical_id` is now part of the stable API contract; any plan extending `OpportunityResponse` will inherit it
- Enrichment now runs automatically daily without manual CLI intervention

---
*Phase: 09-api-feature-polish*
*Completed: 2026-03-24*
