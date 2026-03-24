---
phase: 10-data-population-validation
plan: 01
subsystem: database
tags: [normalizers, backfill, sqlite, sqlalchemy, pytest]

# Dependency graph
requires:
  - phase: 04-data-quality
    provides: ELIGIBILITY_CODE_MAP, normalize_eligibility_codes(), normalizers.py pattern
provides:
  - CATEGORY_CODE_MAP and FUNDING_INSTRUMENT_MAP in normalizers.py
  - normalize_category() and normalize_funding_instrument() functions
  - All 81K Grants.gov records with human-readable eligibility, category, and funding_instrument
  - Backfill script scripts/backfill_normalization.py
affects: [phase-10-plans-02+, api-responses, opportunity-search-results]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw SQL SELECT for ORM queries on Opportunity model — avoids search_vector column not present in SQLite schema"
    - "Module-level dict constant pattern for code maps (CATEGORY_CODE_MAP, FUNDING_INSTRUMENT_MAP) matching ELIGIBILITY_CODE_MAP"

key-files:
  created:
    - grantflow/normalizers.py (CATEGORY_CODE_MAP, FUNDING_INSTRUMENT_MAP, normalize_category, normalize_funding_instrument added)
    - scripts/backfill_normalization.py
  modified:
    - tests/test_normalizers.py (21 new tests added)
    - grantflow/ingest/grants_gov.py (normalize_category and normalize_funding_instrument wired into REST and XML paths)
    - grantflow/ingest/sam_gov.py (normalize_funding_instrument wired in)

key-decisions:
  - "Raw SQL SELECT used in backfill script (not ORM) — Opportunity ORM query includes search_vector which does not exist in SQLite schema; same pattern as assign_canonical_ids"
  - "normalize_category and normalize_funding_instrument return None for empty/None (not empty string) — consistent with normalize_agency_name contract"

patterns-established:
  - "Backfill scripts use raw SQL SELECT + explicit UPDATE — never ORM query on Opportunity due to search_vector column mismatch"

requirements-completed: [QUAL-01]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 10 Plan 01: Data Population & Validation Summary

**CATEGORY_CODE_MAP + FUNDING_INSTRUMENT_MAP normalizers added to normalizers.py, wired into grants_gov.py and sam_gov.py, and all 81,856 existing Grants.gov records backfilled from raw codes (D, CA) to human-readable labels (Discretionary, Cooperative Agreement)**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T22:43:08Z
- **Completed:** 2026-03-24T22:46:21Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `normalize_category()` and `normalize_funding_instrument()` to normalizers.py with 21 new tests (71 total pass)
- Wired both normalizers into grants_gov.py (REST and XML paths) and normalize_funding_instrument into sam_gov.py
- Ran backfill on all 81,856 Grants.gov records; spot-check confirms bare_elig=0, raw_cat=0, raw_fi=0

## Task Commits

Each task was committed atomically:

1. **Task 1: Add category and funding_instrument normalizers with tests** - `80aa92c` (feat)
2. **Task 2: Backfill normalization on all existing records** - `962b89f` (feat)

**Plan metadata:** `(pending docs commit)` (docs: complete plan)

_Note: TDD tasks may have multiple commits (test → feat → refactor). Task 1 used TDD: RED (import error) → GREEN (functions added) in single commit._

## Files Created/Modified

- `grantflow/normalizers.py` - Added CATEGORY_CODE_MAP, FUNDING_INSTRUMENT_MAP, normalize_category(), normalize_funding_instrument()
- `tests/test_normalizers.py` - Added TestNormalizeCategory (10 tests) and TestNormalizeFundingInstrument (9 tests)
- `grantflow/ingest/grants_gov.py` - Imported and applied normalize_category/normalize_funding_instrument in both REST and XML paths
- `grantflow/ingest/sam_gov.py` - Imported and applied normalize_funding_instrument in ingest loop
- `scripts/backfill_normalization.py` - Standalone backfill script using raw SQL; scanned 81,856 records, updated all

## Decisions Made

- Raw SQL SELECT used in backfill script (not ORM) because SQLAlchemy ORM query on Opportunity includes search_vector which does not exist in SQLite schema. Same pattern established in Phase 4 for assign_canonical_ids.
- normalize_category() and normalize_funding_instrument() return None for empty/None input — consistent with normalize_agency_name() contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used raw SQL in backfill script instead of ORM**
- **Found during:** Task 2 (Backfill normalization)
- **Issue:** ORM query `session.query(Opportunity)` failed with `sqlite3.OperationalError: no such column: opportunities.search_vector`
- **Fix:** Replaced ORM query with raw SQL SELECT on required columns only (id, eligible_applicants, category, funding_instrument) and raw SQL UPDATE — same pattern documented in Phase 4 decision and used by assign_canonical_ids
- **Files modified:** scripts/backfill_normalization.py
- **Verification:** Script ran successfully, updated all 81,856 records, spot-check query confirmed 0 bare codes remaining
- **Committed in:** 962b89f (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Fix was essential for correctness. Same known issue pattern from prior phase. No scope creep.

## Issues Encountered

- ORM query on Opportunity model fails with search_vector error on SQLite — resolved by switching to raw SQL (known project pattern from Phase 4).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 81K Grants.gov records now have human-readable labels for eligibility, category, and funding_instrument
- New ingestions via grants_gov.py (REST + XML paths) and sam_gov.py will produce normalized values automatically
- Ready for Phase 10 Plan 02 (pipeline execution and validation for SBIR, SAM.gov, state scrapers)

---
*Phase: 10-data-population-validation*
*Completed: 2026-03-24*
