---
phase: 02-pipeline-hardening
plan: "02"
subsystem: infra
tags: [apscheduler, structlog, pipeline, pipelinerun, sbir, usaspending, grants-gov, incremental-ingest]

requires:
  - phase: 02-pipeline-hardening-01
    provides: PipelineRun model, bind_source_logger, database migrations

provides:
  - APScheduler AsyncIOScheduler wired into FastAPI lifespan firing daily at 02:00 UTC
  - PipelineRun rows written per source after every run_all_ingestion() execution
  - SBIR solicitations HTTP retry with 3x exponential backoff (1s/2s/4s)
  - SBIR opportunity_status derived from close_date (was always NULL)
  - USAspending incremental mode: uses last successful PipelineRun.completed_at - 2d as start_date when run < 36h old
  - structlog bound loggers in all three ingest modules and run_all.py orchestrator
  - Agency code generation fixed: re.sub('[^A-Z0-9]', '_', name.upper())[:50] instead of lossy .replace(' ', '_')

affects: [03-search-api, 04-admin-dashboard, pipeline-monitoring]

tech-stack:
  added: [apscheduler==3.11.2, tzlocal==5.3.1]
  patterns:
    - _write_pipeline_run() helper in run_all.py decouples PipelineRun writes from per-source ingest functions
    - Incremental mode pattern: query last successful PipelineRun, check age < 36h, subtract 2-day buffer
    - SBIR retry pattern: for/else loop with time.sleep(2**attempt) — no extra dependency
    - run_in_executor pattern for running sync ingest from async scheduler context

key-files:
  created: []
  modified:
    - grantflow/app.py
    - grantflow/ingest/run_all.py
    - grantflow/ingest/grants_gov.py
    - grantflow/ingest/sbir.py
    - grantflow/ingest/usaspending.py

key-decisions:
  - "AsyncIOScheduler run_in_executor pattern: run_all_ingestion is sync (SQLAlchemy sync sessions); run_in_executor prevents event loop blocking"
  - "misfire_grace_time=3600: server restart within 1h of 02:00 still fires the missed job"
  - "In-memory APScheduler job store: job registered from code on every startup, no persistent store needed"
  - "_write_pipeline_run() in run_all.py (not inside each ingester): keeps per-source PipelineRun logic centralised; ingesters stay focused on data work"
  - "SBIR retry for/else: no tenacity/retry library dependency; loop body covers only the solicitations API call where retries are needed"
  - "USAspending incremental 36h window: tolerates daily runs with drift; 2-day buffer covers late-arriving data"

patterns-established:
  - "Incremental ingest pattern: query PipelineRun for last success, check age, subtract buffer days from start_date"
  - "Retry pattern: for attempt in range(3) / except / time.sleep(2**attempt) / else: raise"
  - "PipelineRun write helper: _write_pipeline_run(source, result_dict, started_at) called after each source in orchestrator"

requirements-completed: [PIPE-01, PIPE-02, PIPE-03, PIPE-06]

duration: 15min
completed: 2026-03-24
---

# Phase 02 Plan 02: Pipeline Hardening — Scheduler + Ingester Hardening Summary

**APScheduler daily cron at 02:00 UTC in FastAPI lifespan, PipelineRun rows per source, SBIR retry/status fix, USAspending incremental lookback, structlog bound loggers across all ingesters**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T17:54:56Z
- **Completed:** 2026-03-24T17:59:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- APScheduler 3.11.2 wired into FastAPI lifespan; `daily_ingestion` job fires at 02:00 UTC via `CronTrigger`; sync `run_all_ingestion` runs in executor to avoid blocking the event loop
- All three ingesters (`grants_gov`, `usaspending`, `sbir`) and the `run_all` orchestrator now use `bind_source_logger` from the structlog pipeline established in Plan 01
- `run_all.py` writes a `PipelineRun` row per source after each ingest via `_write_pipeline_run()` helper, capturing `records_processed/added/updated/failed`, `status`, timing, and error messages
- SBIR: `import hashlib` moved to module top; `opportunity_status` derived from `close_date` comparison (was always NULL); solicitations API call wrapped in 3-retry loop with exponential backoff
- USAspending: incremental mode queries last successful `PipelineRun` — if < 36h old, uses `completed_at - 2 days` as `start_date` instead of the 2-year full lookback; agency code generation replaced with safe regex slug

## Task Commits

1. **Task 1: Wire APScheduler into FastAPI lifespan** — `50b3745` (feat)
2. **Task 2: Harden ingesters** — `78c76fb` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `grantflow/app.py` — Added `AsyncIOScheduler` with `CronTrigger(hour=2, timezone="UTC")` in lifespan; `run_in_executor` for sync ingest
- `grantflow/ingest/run_all.py` — `bind_source_logger("pipeline")`; `_write_pipeline_run()` helper; structlog event names for all steps; `skipped` status excluded from failures list
- `grantflow/ingest/grants_gov.py` — `bind_source_logger("grants_gov")`; `records_failed` counter; per-record exception handling in `_upsert_batch`
- `grantflow/ingest/sbir.py` — `import hashlib` at module top; retry loop for solicitations; `opportunity_status` derivation; `records_failed` in stats
- `grantflow/ingest/usaspending.py` — `bind_source_logger("usaspending")`; incremental `start_date` from last `PipelineRun`; `re.sub` agency code slug; `records_failed` in stats

## Decisions Made

- `run_in_executor` chosen over converting `run_all_ingestion` to async: avoids rewriting all SQLAlchemy sessions; async migration is reserved for future phase
- `_write_pipeline_run()` centralised in `run_all.py` rather than inside each ingester: keeps ingesters focused on data work; orchestrator owns run accounting
- Retry `for/else` pattern without `tenacity`: no new dependency; only the solicitations call is retried (awards use streaming CSV, different failure mode)
- USAspending 36h age window: accommodates daily runs with up to 12h drift before falling back to full 2-year lookback

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `run_all.py` already imported `ingest_sam_gov` from a non-existent module**
- **Found during:** Task 2 (reading `run_all.py` before editing)
- **Issue:** The current `run_all.py` on disk already imports from `grantflow.ingest.sam_gov` and runs a 4-source pipeline. The `sam_gov.py` module did exist on disk (written by Plan 01) but wasn't in the plan's file list — confirmed it was complete and already using `PipelineRun` + `bind_source_logger`
- **Fix:** No action needed — `sam_gov.py` was already correct; retained the 4-source orchestration in `run_all.py` and preserved the `ingest_sam_gov` call
- **Files modified:** None (verified existing file was correct)
- **Verification:** Import succeeds; all 17 tests pass

---

**Total deviations:** 1 (investigation only, no fix needed)
**Impact on plan:** No scope change. Pre-existing work from Plan 01 was already correct.

## Issues Encountered

- `run_all.py` had been modified on disk between Plan 01 completion and this execution (linter/tool expanded it to 4-source + SAM.gov). Re-read before editing resolved the conflict cleanly.

## User Setup Required

None — no external service configuration required for the scheduler or ingest hardening.

## Next Phase Readiness

- Daily automated ingestion is live; data will stay fresh without manual intervention
- `PipelineRun` rows are being written — pipeline monitoring dashboard (Plan 03) can query them immediately
- All Phase 1 tests still passing (17/17)
- SAM.gov ingest skips cleanly when `SAM_GOV_API_KEY` not set — no production errors

---
*Phase: 02-pipeline-hardening*
*Completed: 2026-03-24*
