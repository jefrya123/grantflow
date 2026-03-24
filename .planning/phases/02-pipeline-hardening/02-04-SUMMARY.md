---
phase: 02-pipeline-hardening
plan: "04"
subsystem: ingest
tags: [grants-gov, rest-api, xml, dual-source, httpx, fallback-strategy]

requires:
  - phase: 02-pipeline-hardening
    plan: "01"
    provides: "structlog pipeline logger (bind_source_logger) and PipelineRun model"

provides:
  - "_ingest_via_rest(): paginates Grants.gov search2 REST API, returns None on 5xx/network/threshold failure"
  - "_ingest_via_xml(): extracted XML bulk-extract logic as standalone helper returning None on failure"
  - "ingest_grants_gov(): REST-first, XML-fallback strategy with GRANTS_GOV_USE_REST force-flag"
  - "GRANTS_GOV_REST_API_BASE and GRANTS_GOV_USE_REST config env vars"
  - "6 unit tests covering REST/XML strategy paths in tests/test_grants_gov_rest.py"

affects:
  - "phase: 03-api-key-infrastructure (Grants.gov ingest entry point unchanged)"
  - "Any future plan that enables REST-only migration"

tech-stack:
  added: []
  patterns:
    - "Dual-source strategy: try REST first, return None to signal fallback; caller decides next path"
    - "MIN_REST_THRESHOLD guard: treat REST as unreliable when record count is suspiciously low"
    - "Same composite id format (grants_gov_{source_id}) for both paths ensures upsert deduplication"
    - "path logged in PipelineRun.extra JSON field for migration progress visibility"

key-files:
  created:
    - tests/test_grants_gov_rest.py
  modified:
    - grantflow/ingest/grants_gov.py
    - grantflow/config.py

key-decisions:
  - "REST returns None on any failure (5xx, network, below-threshold) rather than raising — clean fallback contract"
  - "MIN_REST_THRESHOLD=100: REST API returning fewer than 100 records is treated as unreliable, not a valid partial response"
  - "MAX_REST_PAGES=200 cap (5,000 records max via REST) prevents infinite pagination against a misbehaving API"
  - "GRANTS_GOV_USE_REST=true causes hard error when REST unavailable (not silent XML fallback) — makes migration testing explicit"
  - "records_failed field preserved from 02-01 in both REST and XML stats dicts for consistency"

patterns-established:
  - "Ingest helper pattern: private helper returns dict|None; None = caller should try next path"
  - "REST pagination: POST search2 with startRecordNum offset; stop when oppHits empty or count exhausted"

requirements-completed: [PIPE-08]

duration: 2min
completed: 2026-03-24
---

# Phase 02 Plan 04: Grants.gov Dual-Source Ingest Summary

**Grants.gov REST API (search2) added as primary ingest path with automatic XML bulk-extract fallback, controlled by MIN_REST_THRESHOLD=100 guard and GRANTS_GOV_USE_REST force flag**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-24T13:58:38-04:00
- **Completed:** 2026-03-24T13:59:46-04:00
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments

- Added `_ingest_via_rest()`: paginates the Grants.gov `/v1/api/search2` endpoint, maps `oppHit` fields to the Opportunity schema, returns `None` on any 5xx, network error, or record count below threshold
- Extracted existing XML logic into `_ingest_via_xml()` helper with the same `dict | None` return contract
- `ingest_grants_gov()` now implements REST-first strategy: tries REST, falls back to XML on `None`, errors if both fail; `GRANTS_GOV_USE_REST=true` forces REST-only for migration testing
- 6 unit tests covering 5xx failure, below-threshold failure, connection error, REST success path, XML fallback wiring, and REST-only error mode

## Task Commits

1. **Task 1: Add REST API config vars and _ingest_via_rest() helper** - `fbde0fa` (feat)
2. **Task 2: Wire dual-source strategy into ingest_grants_gov()** - `1adfeb1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/ingest/grants_gov.py` - Rewritten with REST path, XML path extracted, dual-source strategy in public entry point
- `grantflow/config.py` - Added `GRANTS_GOV_REST_API_BASE` and `GRANTS_GOV_USE_REST` env vars
- `tests/test_grants_gov_rest.py` - 6 unit tests for REST/XML strategy paths

## Decisions Made

- `_ingest_via_rest()` returns `None` (not raises) on any failure — clean contract that lets `ingest_grants_gov()` decide the fallback path without exception handling at the caller
- `MIN_REST_THRESHOLD=100`: a healthy Grants.gov response has thousands of records; fewer than 100 indicates a degraded API worth falling back from
- `MAX_REST_PAGES=200` (5,000 record cap) prevents infinite pagination if the API returns unexpected data
- `GRANTS_GOV_USE_REST=true` mode produces a hard error when REST is unavailable — this is intentional; silent XML fallback in REST-only mode would defeat the purpose of migration validation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Preserved records_failed field from 02-01**
- **Found during:** Task 1 (reviewing current file state)
- **Issue:** The 02-01 plan had already added `records_failed` tracking to `_upsert_batch()` and the stats dict; the new REST and XML helpers needed to carry the same field for consistency
- **Fix:** Included `records_failed` in all stats dicts and in `_upsert_batch()` (already present from 02-01 — preserved, not dropped)
- **Files modified:** grantflow/ingest/grants_gov.py
- **Verification:** All tests pass; no regression to 02-01 changes
- **Committed in:** fbde0fa (Task 1 commit)

**2. [Rule 1 - Bug] Test mock pagination side_effect fix**
- **Found during:** Task 2 (running test suite)
- **Issue:** `test_rest_returns_stats_above_threshold` returned 400 records instead of 100 — `patch("httpx.post", return_value=...)` re-uses same response on every page call, so 4 pages were fetched
- **Fix:** Changed to `side_effect=[page1_response, empty_response]` so pagination stops after the first page
- **Files modified:** tests/test_grants_gov_rest.py
- **Verification:** All 6 tests pass
- **Committed in:** 1adfeb1 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical preservation, 1 test bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- File had been modified by 02-01 (structlog logger, `records_failed` field, `bind_source_logger`) between when the plan was written and execution — incorporated all existing changes into the rewrite.

## User Setup Required

None — no external service configuration required beyond the existing `GRANTFLOW_DATABASE_URL`. The `GRANTS_GOV_USE_REST` and `GRANTS_GOV_REST_API_BASE` env vars are optional overrides with sensible defaults.

## Next Phase Readiness

- Grants.gov ingest is now migration-ready: REST path can be validated with `GRANTS_GOV_USE_REST=true` before XML deprecation
- Path used per run is visible in `PipelineRun.extra` for 30-day stability tracking requirement
- No blockers for Phase 3 (API key infrastructure)

---
*Phase: 02-pipeline-hardening*
*Completed: 2026-03-24*
