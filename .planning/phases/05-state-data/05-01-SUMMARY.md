---
phase: 05-state-data
plan: 01
subsystem: ingest
tags: [state-scraping, abstract-base-class, tdd, legal-review, python]

requires:
  - phase: 04-data-quality
    provides: normalizers.py (normalize_date, normalize_agency_name, etc.) used in CA normalization scaffold

provides:
  - BaseStateScraper abstract class with run()/fetch_records()/normalize_record() contract
  - make_opportunity_id() generating state_{code}_{id} prefix format
  - TDD test scaffolds for STATE-01, STATE-04, STATE-05 behaviors
  - Legal review documentation for all 5 target portals
  - STATE_SCRAPER_BATCH_SIZE and STATE_SCRAPER_REQUEST_DELAY config vars

affects: [05-02-state-scrapers, 05-03-state-scheduler, pipeline-monitoring]

tech-stack:
  added: []
  patterns:
    - "BaseStateScraper: abstract class with class attributes source_name/state_code; run() implements full upsert loop; subclasses only implement fetch_records()/normalize_record()"
    - "Session injection: run(session=None) accepts external session for tests; creates own SessionLocal() when not provided"
    - "xfail scaffolding: future-plan tests marked pytest.mark.xfail(strict=False) so they don't block current plan verification but document expected behavior"
    - "Batch commit: commits every STATE_SCRAPER_BATCH_SIZE records (default 100) to bound memory usage"

key-files:
  created:
    - grantflow/ingest/state/__init__.py
    - grantflow/ingest/state/base.py
    - grantflow/ingest/state/LEGAL_REVIEW.md
    - tests/test_state_scrapers.py
    - tests/test_state_monitor.py
  modified:
    - grantflow/config.py

key-decisions:
  - "Session injection pattern: BaseStateScraper.run() accepts optional session for test isolation; creates own SessionLocal() in production — matches existing monitor.py pattern"
  - "xfail for cross-plan scaffolds: test_normalize_ca_record and test_scheduler_weekly_job are xfail(strict=False) — document future contracts without blocking current verification"
  - "test_state_monitor.py tests left RED intentionally — check_zero_records() and check_staleness_with_thresholds() are Plan 03 deliverables"
  - "Colorado marked CONDITIONAL in legal review — no centralized open data mandate; requires per-portal ToS/robots.txt verification before scraping"

requirements-completed: [STATE-01, STATE-03]

duration: 15min
completed: 2026-03-24
---

# Phase 5 Plan 01: State Scraping Infrastructure Summary

**Abstract BaseStateScraper class with batch upsert, session injection, TDD scaffolds for all 5 state requirements, and legal review approving CA/NY/IL/TX portals**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-24T19:26:39Z
- **Completed:** 2026-03-24T19:40:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `BaseStateScraper` abstract class with correct ingestor contract stats dict shape, batch upsert (100/commit), session injection for test isolation
- TDD scaffolds: 3 green tests + 2 xfail scaffolds for Plans 02/03; RED monitor tests document Plan 03 contracts
- Legal review for all 5 portals: CA/NY/IL/TX APPROVED, CO CONDITIONAL pending ToS verification

## Task Commits

Each task was committed atomically:

1. **Task 1: BaseStateScraper infrastructure and TDD test scaffolds** - `00ba417` (feat)
2. **Task 2: Legal review documentation** - `de20495` (docs)

**Plan metadata:** _(final docs commit — see below)_

## Files Created/Modified

- `grantflow/ingest/state/__init__.py` — Package init for state scraper module
- `grantflow/ingest/state/base.py` — `BaseStateScraper` abstract base class: `run()`, `fetch_records()`, `normalize_record()`, `make_opportunity_id()`; batch upsert with session injection
- `grantflow/ingest/state/LEGAL_REVIEW.md` — Per-portal legal review with checklist results and approval status for all 5 portals
- `grantflow/config.py` — Added `STATE_SCRAPER_BATCH_SIZE` and `STATE_SCRAPER_REQUEST_DELAY` config vars
- `tests/test_state_scrapers.py` — GREEN tests for stats shape, ID prefix, skip-on-None; xfail scaffolds for CA normalization (Plan 02) and scheduler job (Plan 03)
- `tests/test_state_monitor.py` — RED scaffolds for `check_zero_records()` and `check_staleness_with_thresholds()` (Plan 03 deliverables)

## Decisions Made

- **Session injection:** `run(session=None)` accepts external session for test isolation; creates own `SessionLocal()` when absent. Matches existing `monitor.py` pattern, enables `db_session` fixture usage in tests.
- **xfail for cross-plan contracts:** `test_normalize_ca_record` and `test_scheduler_weekly_job` use `pytest.mark.xfail(strict=False)` — documents expected behavior without blocking this plan's CI.
- **Monitor tests intentionally RED:** `test_state_monitor.py` fails with `ImportError` for `check_zero_records` and `check_staleness_with_thresholds` — these are Plan 03 deliverables, RED state is correct and expected.
- **Colorado CONDITIONAL:** No centralized open data mandate found; ToS/robots.txt must be verified before any scraping begins.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 02 can immediately subclass `BaseStateScraper` for California (CKAN API)
- `test_normalize_ca_record` xfail will auto-pass once Plan 02 creates `california.py`
- Plan 03 must implement `check_zero_records()` and `check_staleness_with_thresholds()` in `pipeline/monitor.py` to turn the RED monitor tests GREEN
- Colorado scraper (Plan 02) is blocked until legal review CONDITIONAL is resolved

---
*Phase: 05-state-data*
*Completed: 2026-03-24*
