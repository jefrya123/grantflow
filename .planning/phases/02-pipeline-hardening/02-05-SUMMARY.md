---
phase: 02-pipeline-hardening
plan: "05"
subsystem: pipeline-monitoring
tags: [monitoring, staleness, cfda, cross-reference, health-endpoint]
dependency_graph:
  requires: [02-02, 02-03, 02-04]
  provides: [staleness-alerting, cfda-normalization, award-cross-linking, health-freshness]
  affects: [grantflow/api/routes.py, grantflow/ingest/run_all.py]
tech_stack:
  added: [smtplib]
  patterns: [per-source-freshness-report, post-ingest-normalization-pass, smtp-alert-with-fallback]
key_files:
  created:
    - grantflow/pipeline/monitor.py
    - grantflow/pipeline/cfda_link.py
    - tests/test_monitor.py
    - tests/test_cfda_link.py
  modified:
    - grantflow/ingest/run_all.py
    - grantflow/api/routes.py
decisions:
  - "SMTP failures in check_staleness() are caught and logged, never raised — monitoring never crashes the pipeline"
  - "normalize_cfda() uses regex + split instead of ilike — eliminates format mismatch at ingest time, avoids full table scans"
  - "never_run status distinct from stale — sources that have never run are not alerts, just not yet ingested"
  - "link_opportunities_to_awards() uses .contains() not ilike — consistent with CONCERNS.md note on avoiding full table scans"
metrics:
  duration_seconds: 139
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_created: 4
  files_modified: 2
---

# Phase 02 Plan 05: Staleness Monitor and CFDA Cross-Reference Summary

**One-liner:** 48h staleness alerting via structlog ERROR + optional SMTP email, plus CFDA normalization pass that cross-links Opportunities to historical Awards.

## What Was Built

### Task 1: Pipeline Staleness Monitor

`grantflow/pipeline/monitor.py` provides two public functions:

**`get_freshness_report(session=None) -> dict`**
- Queries `pipeline_runs` for `max(completed_at)` per known source where `status='success'`
- Returns per-source dict with `status` (`ok` | `stale` | `never_run`), `last_success` (ISO 8601), `hours_since` (float)
- Accepts optional session (supports both standalone and in-transaction call patterns)

**`check_staleness(session=None) -> list[str]`**
- Calls `get_freshness_report()`, logs `ERROR stale_source_detected` for each stale source
- If `GRANTFLOW_ALERT_EMAIL` env var is set, sends plain-text email via smtplib using `SMTP_HOST`/`SMTP_PORT`
- SMTP failures are logged but never raised — monitoring never crashes the pipeline
- Returns list of stale source names (empty = all sources fresh)

**Wired into `run_all.py`:** `check_staleness()` is called after all four source pipelines complete. Stale sources are added to the summary dict and logged at WARNING level.

### Task 2: CFDA Cross-Reference Linker and Health Freshness

`grantflow/pipeline/cfda_link.py` provides two public functions:

**`normalize_cfda(raw: str | None) -> str`**
- Handles all known variant formats: `84-007`, `084.007`, `84.7`, `84 007`, `  84.007  `
- Output always canonical: prefix stripped of leading zeros, suffix zero-padded to 3 digits, dot separator
- Returns empty string for None/empty input

**`link_opportunities_to_awards(session=None) -> dict`**
- Fetches all Opportunities with non-null cfda_numbers
- Normalizes each CFDA value in-place (updates DB row if value changed)
- Counts Award records matching each normalized CFDA via `.contains()`
- Returns `{opportunities_processed, cfda_normalized, award_links_found}`

**Wired into `run_all.py`:** Called after `check_staleness()`, stats added to summary dict.

**Health endpoint extended:** `/api/v1/health` now includes `source_freshness` key with the full `get_freshness_report()` output, exposing per-source `ok` | `stale` | `never_run` status.

## Tests

- `tests/test_monitor.py` — 6 tests: never_run, ok, stale, ignores failed runs, stale list return, empty list when fresh
- `tests/test_cfda_link.py` — 12 tests: 8 normalize_cfda unit tests (all format variants), 4 DB integration tests (empty DB, normalize in-place, award matching, null CFDA skipped)
- Full suite: 35 tests, all pass

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

| Claim | Verified |
|-------|---------|
| `grantflow/pipeline/monitor.py` exists | FOUND |
| `grantflow/pipeline/cfda_link.py` exists | FOUND |
| `tests/test_monitor.py` exists | FOUND |
| `tests/test_cfda_link.py` exists | FOUND |
| Task 1 commit `7e4ed18` | FOUND |
| Task 2 commit `7c4df63` | FOUND |
| 35 tests pass | VERIFIED |

## Self-Check: PASSED
