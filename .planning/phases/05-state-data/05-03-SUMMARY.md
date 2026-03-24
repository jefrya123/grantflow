---
phase: 05-state-data
plan: "03"
subsystem: pipeline-monitoring
tags: [monitoring, scheduling, orchestration, state-scrapers, apscheduler]
dependency_graph:
  requires: [05-01]
  provides: [run_state_ingestion, check_zero_records, weekly_state_ingestion_job]
  affects: [grantflow/pipeline/monitor.py, grantflow/ingest/run_state.py, grantflow/app.py, grantflow/ingest/run_all.py]
tech_stack:
  added: []
  patterns:
    - "Per-source stale threshold dict replaces single global constant"
    - "ZERO_RECORD_SOURCES = [s for s in KNOWN_SOURCES if s.startswith('state_')] — auto-derives state sources"
    - "Module-level scheduler in app.py enables test inspection without app startup"
    - "Lazy scraper imports in _get_scrapers() prevent import-time failures if scrapling absent"
key_files:
  created:
    - grantflow/ingest/run_state.py
  modified:
    - grantflow/pipeline/monitor.py
    - grantflow/app.py
    - grantflow/ingest/run_all.py
    - tests/test_state_monitor.py
    - tests/test_state_scrapers.py
    - tests/test_monitor.py
decisions:
  - "Module-level scheduler in app.py: jobs still added inside lifespan, but scheduler object exposed at module scope for test introspection without full app startup"
  - "test_scheduler_weekly_job replicates scheduler setup inline rather than importing from app.py lifespan — avoids async lifecycle complexity in sync tests"
  - "check_zero_records() called from both run_state_ingestion (after weekly runs) and run_all_ingestion (daily catch) — two detection paths for faster alerting"
  - "STALE_THRESHOLD_HOURS=48 kept as backward-compat alias — existing code that imports it continues to work"
metrics:
  duration_minutes: 3
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_modified: 7
---

# Phase 05 Plan 03: State Scraper Monitoring, Scheduling, and Orchestration Summary

Zero-record detection for state scrapers plus per-source staleness thresholds (240h weekly vs 48h federal), `run_state.py` orchestrator, and APScheduler weekly job at Sunday 03:00 UTC completing the operational infrastructure for state data.

## What Was Built

### Task 1: Extended monitor.py (TDD)

`grantflow/pipeline/monitor.py` gained three major changes:

1. `STALE_THRESHOLDS` dict replaces the single `STALE_THRESHOLD_HOURS = 48` constant. Federal sources keep 48h; state sources (weekly scrapers) get 240h (10 days). The old constant is kept as a backward-compat alias.

2. `KNOWN_SOURCES` expanded from 4 federal to 9 total (4 federal + 5 state). `get_freshness_report()` uses `STALE_THRESHOLDS.get(source, FEDERAL_STALE_THRESHOLD_HOURS)` for per-source threshold lookup.

3. `check_zero_records(session)` — queries the most recent successful `PipelineRun` per state source. If `records_processed == 0`, logs ERROR and calls `_send_zero_records_alert()`. Returns list of broken source names.

### Task 2: run_state.py, app.py, run_all.py

`grantflow/ingest/run_state.py` — new orchestrator following the same pattern as `run_all.py`:
- Lazy-imports all 5 state scrapers in `_get_scrapers()` to avoid import-time failures
- Calls `_write_pipeline_run()` for each scraper result (reuses run_all's accounting)
- Calls `check_zero_records()` after all scrapers complete
- Runs `assign_canonical_ids()` for dedup

`grantflow/app.py`:
- `scheduler` promoted to module-level `AsyncIOScheduler()` instance
- `weekly_state_ingestion` job added in `lifespan()` at `CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC")`

`grantflow/ingest/run_all.py`:
- Added `check_zero_records()` call after the existing `check_staleness()` in step 7b — daily pipeline now also detects broken state scrapers.

## Test Results

```
tests/test_state_monitor.py::test_zero_records_detection PASSED
tests/test_state_monitor.py::test_zero_records_ignores_federal PASSED
tests/test_state_monitor.py::test_zero_records_ignores_error_runs PASSED
tests/test_state_monitor.py::test_state_stale_threshold PASSED
tests/test_state_monitor.py::test_federal_stale_threshold_unchanged PASSED
tests/test_state_scrapers.py::test_scheduler_weekly_job PASSED
tests/test_monitor.py — 6 passed (backward compat verified)
Full suite: 146 passed, 1 xpassed
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_monitor.py hardcoded 4-source set assertion**
- **Found during:** Task 1 GREEN phase
- **Issue:** `test_freshness_report_never_run` asserted `set(report.keys()) == {"grants_gov", "usaspending", "sbir", "sam_gov"}`. After KNOWN_SOURCES expanded to 9 sources, this assertion failed.
- **Fix:** Changed assertion to `set(report.keys()) == set(KNOWN_SOURCES)` and added targeted checks for the 4 federal sources.
- **Files modified:** `tests/test_monitor.py`
- **Commit:** fc63f0e

## Commits

| Hash | Message |
|------|---------|
| 353242d | test(05-03): add failing tests for zero-record detection and per-source stale thresholds |
| fc63f0e | feat(05-03): extend monitor.py with zero-record detection and per-source stale thresholds |
| 820c67a | feat(05-03): create run_state.py orchestrator and add weekly APScheduler job |

## Self-Check: PASSED
