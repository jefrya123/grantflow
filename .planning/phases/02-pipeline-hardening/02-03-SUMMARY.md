---
phase: 02-pipeline-hardening
plan: "03"
subsystem: ingest
tags: [sam.gov, httpx, incremental-ingest, rate-limiting, pipeline]

requires:
  - phase: 02-pipeline-hardening/02-01
    provides: PipelineRun model, IngestionLog model, bind_source_logger pattern

provides:
  - SAM.gov incremental ingestor (grantflow/ingest/sam_gov.py)
  - ingest_sam_gov() function — rate-limit-aware, incremental, skip-safe
  - SAM_GOV_API_KEY and SAM_GOV_API_BASE config vars
  - run_all orchestrator updated to 4-step pipeline

affects: [03-api-layer, 04-search, 05-scheduler]

tech-stack:
  added: []
  patterns:
    - "Incremental ingest: query last successful PipelineRun.completed_at, subtract 1-day buffer, use as postedFrom"
    - "Rate-limit guard: HTTP 429 triggers clean break with status='partial', not exception"
    - "API key guard: empty SAM_GOV_API_KEY returns status='skipped' before any I/O"
    - "Dual log writes: IngestionLog (health endpoint) + PipelineRun (incremental cursor) per run"

key-files:
  created:
    - grantflow/ingest/sam_gov.py
    - tests/test_sam_gov.py
  modified:
    - grantflow/config.py
    - grantflow/ingest/run_all.py

key-decisions:
  - "30-day lookback on first run (not full history) — stays within 10 req/day public limit on initial setup"
  - "PAGE_SIZE=10, MAX_PAGES=50 — 500 records/run max; conservative until API key with higher quota obtained"
  - "status='partial' (not 'error') on rate-limit hit — partial data is usable, not a failure"
  - "agency_name extracted from fullParentPathName last segment — SAM.gov path is pipe-delimited hierarchy"

patterns-established:
  - "Incremental cursor via PipelineRun: any future incremental ingestor should follow same last-run query pattern"
  - "API key guard at function entry: check config var before any DB or HTTP I/O"

requirements-completed: [PIPE-04]

duration: 15min
completed: 2026-03-24
---

# Phase 2 Plan 3: SAM.gov Incremental Ingestor Summary

**Rate-limit-aware SAM.gov contract opportunities ingestor using 30-day lookback on first run, PipelineRun cursor for incremental fetches, and clean 429 handling returning status='partial'**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T18:10:00Z
- **Completed:** 2026-03-24T18:25:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Implemented `ingest_sam_gov()` with true incremental design — uses last successful PipelineRun completion timestamp as the `postedFrom` cursor, with 1-day buffer for late-arriving data
- Rate-limit safety: HTTP 429 triggers a clean partial stop (commits what was fetched, returns `status="partial"`) instead of crashing
- Missing API key guard: empty `SAM_GOV_API_KEY` returns `status="skipped"` immediately with a warning log — no DB writes, no HTTP calls
- Integrated as STEP 4/4 in `run_all_ingestion()` orchestrator; all existing step labels updated
- 6 tests added (skip-without-key + 5 date parsing variants), all 11 suite tests pass

## Task Commits

1. **Task 1: Add SAM.gov config vars and ingestor module** - `a5eee31` (feat)
2. **Task 2: Register SAM.gov in run_all orchestrator** - `64c3d13` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/ingest/sam_gov.py` - Full SAM.gov ingestor: incremental pagination, rate-limit handling, upsert, dual log writes
- `grantflow/config.py` - Added `SAM_GOV_API_KEY` and `SAM_GOV_API_BASE` env var config
- `grantflow/ingest/run_all.py` - Imports and calls `ingest_sam_gov()` as STEP 4/4; step labels updated
- `tests/test_sam_gov.py` - Skip-without-key test + `_parse_sam_date` coverage (ISO, plain date, slash format, None, empty)

## Decisions Made

- **30-day lookback on first run** (not full history): SAM.gov public limit is 10 req/day; at PAGE_SIZE=10 that is 100 records max before exhaustion. 30-day window keeps initial fetch within budget.
- **PAGE_SIZE=10, MAX_PAGES=50**: 500-record cap per run is conservative until a registered API key with higher quota (default 1,000/day) is obtained. Easily tunable via constants.
- **status='partial' on 429**: Rate-limited runs still produced valid data. Marking as 'error' would prevent those records from being used as the incremental cursor in the next run.
- **agency_name from fullParentPathName last segment**: SAM.gov returns a pipe-delimited org hierarchy (e.g. "DEPT OF DEFENSE|ARMY|MEDCOM"). Last segment is most specific.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

**SAM.gov API key required for full operation.** Without it, ingestion is skipped with a warning.

To enable:
1. Register a System Account at https://sam.gov → Sign In → System Account Management
2. Request 'Opportunities' data access scope
3. Wait 1-3 business days for approval
4. Set `SAM_GOV_API_KEY=<your-key>` in your environment (`.env` or system env)

Without a key, the public limit is 10 req/day (100 records), which may be sufficient for testing.

## Next Phase Readiness

- SAM.gov ingestion ready; pipeline now has 4 sources (Grants.gov, USAspending, SBIR, SAM.gov)
- SAM.gov data will appear in `opportunities` table with `source='sam_gov'` once API key is set
- Incremental cursor pattern documented — ready to apply to future ingestors in Phase 3+

---
*Phase: 02-pipeline-hardening*
*Completed: 2026-03-24*
