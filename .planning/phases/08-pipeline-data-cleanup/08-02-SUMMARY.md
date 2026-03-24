---
phase: 08-pipeline-data-cleanup
plan: 02
subsystem: ingest/normalization
tags: [sam-gov, normalizers, data-quality, refactor]
requirements: [QUAL-01, QUAL-02, QUAL-05, QUAL-06]

dependency_graph:
  requires: ["08-01"]
  provides: ["sam_gov normalization wiring"]
  affects: ["grantflow/ingest/sam_gov.py", "tests/test_sam_gov.py"]

tech_stack:
  added: []
  patterns:
    - "normalize_date|normalize_eligibility_codes|normalize_agency_name|validate_award_amounts called on opp_data after dict construction"
    - "Wire test pattern: inspect module source for normalizer symbol names"

key_files:
  created: []
  modified:
    - grantflow/ingest/sam_gov.py
    - tests/test_sam_gov.py

decisions:
  - "sam_gov.py normalization block placed after opp_data dict built, before session.get() upsert — matches grants_gov.py established pattern"
  - "_parse_sam_date deleted entirely (not deprecated) — normalize_date handles all same formats plus more, Plan 01 already added fromisoformat pre-pass"
  - "Wire tests use source inspection (open(mod.__file__).read()) — simple, no DB/API mocking required for import verification"

metrics:
  duration: 2min
  completed: 2026-03-24
  tasks_completed: 2
  files_modified: 2
---

# Phase 8 Plan 02: SAM.gov Normalization Wiring Summary

**One-liner:** Wired SAM.gov ingestor through all four shared normalizers and deleted the now-redundant private `_parse_sam_date` function, closing QUAL-01/02/05/06 gaps.

## What Was Built

SAM.gov was the last federal ingestor bypassing `normalizers.py`. This plan wires it through the same pipeline as Grants.gov, USAspending, and SBIR:

- `normalize_date()` replaces `_parse_sam_date()` for `post_date` and `close_date`
- `normalize_eligibility_codes()` applied to `eligible_applicants`
- `normalize_agency_name()` applied to `agency_name`
- `validate_award_amounts(None, None)` called for `award_floor`/`award_ceiling` consistency
- `_parse_sam_date()` function deleted (27 lines removed)

All four federal ingestors now share one normalization pipeline.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Migrate _parse_sam_date tests, add wire tests | b618603 | tests/test_sam_gov.py |
| 2 (GREEN) | Wire sam_gov.py through normalizers, remove _parse_sam_date | aa82150 | grantflow/ingest/sam_gov.py |

## Test Results

- 9/9 tests in `test_sam_gov.py` pass (5 migrated date tests + 3 wire tests + 1 skip test)
- 187 passed, 0 failed in full suite (1 xpassed — pre-existing)
- Zero references to `_parse_sam_date` remain in functional code

## Verification

```
grep normalize_date|normalize_eligibility|normalize_agency|validate_award grantflow/ingest/sam_gov.py
# → 4 import lines + 5 call sites confirmed

grep -rn "_parse_sam_date" grantflow/ tests/
# → only string literals in test assertions (not imports/calls)
```

## Deviations from Plan

None — plan executed exactly as written.

## Requirements Closed

- QUAL-01: SAM.gov eligibility codes normalized via `normalize_eligibility_codes()`
- QUAL-02: SAM.gov agency names normalized via `normalize_agency_name()`
- QUAL-05: SAM.gov dates processed through `normalize_date()` (not private function)
- QUAL-06: `validate_award_amounts()` called on SAM.gov records (no-op for None/None, consistent pattern)
