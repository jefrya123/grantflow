---
phase: 08-pipeline-data-cleanup
plan: "01"
subsystem: normalizers, ingest
tags: [tdd, data-quality, normalization, dead-code]
dependency_graph:
  requires: []
  provides: [normalize_date_tz_aware, fts5_absence_verified, sbir_import_clean]
  affects: [grantflow/normalizers.py, grantflow/ingest/sbir.py]
tech_stack:
  added: []
  patterns: [fromisoformat-prepass, TDD-red-green]
key_files:
  created:
    - tests/test_pipeline_cleanup.py
  modified:
    - grantflow/normalizers.py
    - grantflow/ingest/sbir.py
    - tests/test_normalizers.py
decisions:
  - "fromisoformat pre-pass added before strptime loop — handles full ISO 8601 (TZ offsets, Z suffix) without changing behavior for non-ISO formats"
  - "sbir.py comment rephrased to avoid containing the dead symbol name — avoids false positive in text-search smoke test"
metrics:
  duration_minutes: 8
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_changed: 4
---

# Phase 08 Plan 01: Pipeline Data Cleanup Summary

**One-liner:** `datetime.fromisoformat()` pre-pass added to `normalize_date()` for ISO 8601 timezone-offset support (SAM.gov dates), with smoke tests confirming FTS5 removal and clean sbir.py imports.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Create smoke tests and add normalize_date offset tests | d253162 | tests/test_pipeline_cleanup.py, tests/test_normalizers.py |
| 2 (GREEN) | Fix normalize_date() and document sbir.py imports | 8c41acb | grantflow/normalizers.py, grantflow/ingest/sbir.py |

## What Was Built

**normalize_date() timezone fix (QUAL-05):**
Added a `datetime.fromisoformat()` pre-pass before the `_DATE_FORMATS` strptime loop. This handles ISO 8601 strings with timezone offsets (`2024-03-15T00:00:00-04:00`) and the Z suffix (`2024-03-15T00:00:00Z`) which `strptime` cannot parse. Python 3.13 (in use) supports the full ISO 8601 spec via `fromisoformat`. Existing non-ISO formats (MM/DD/YYYY, YYYYMMDD, etc.) are unaffected — `fromisoformat` rejects them and falls through to the strptime loop.

**sbir.py dead import (QUAL-06):**
Confirmed `validate_award_amounts` was already absent from the import block. Added a comment documenting why it is not imported (SBIR records have no award_floor or award_ceiling fields).

**Smoke tests (FOUND-02):**
Created `tests/test_pipeline_cleanup.py` with two tests:
- `test_no_fts5_references`: scans all `.py` files under `grantflow/` for FTS5/virtual table patterns — confirms FOUND-02 cleanup holds
- `test_sbir_no_dead_import`: reads `sbir.py` as text and asserts the dead symbol name is absent

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Comment text triggered the smoke test's own assertion**
- **Found during:** Task 2 (first GREEN run)
- **Issue:** The plan's suggested comment text `# Note: validate_award_amounts not imported` literally contained the pattern the smoke test searches for, causing `test_sbir_no_dead_import` to fail despite no actual import existing
- **Fix:** Rephrased comment to `# Note: award amount validation is not imported` — semantically equivalent, pattern-safe
- **Files modified:** `grantflow/ingest/sbir.py`
- **Commit:** 8c41acb (included in same Task 2 commit)

## Success Criteria Verification

- [x] `test_no_fts5_references` passes — FOUND-02 resolved
- [x] `test_sbir_no_dead_import` passes — QUAL-06 dead code documented
- [x] `normalize_date("2024-03-15T00:00:00-04:00") == "2024-03-15"` — QUAL-05 resolved
- [x] `normalize_date("2024-03-15T00:00:00Z") == "2024-03-15"` — Z suffix edge case handled
- [x] Full test suite: 184 passed, 1 xpassed — no regressions
