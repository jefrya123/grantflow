---
phase: 04-data-quality
plan: 01
subsystem: database
tags: [normalization, data-quality, eligibility-codes, agency-names, dates]

# Dependency graph
requires:
  - phase: 03-api-key-infrastructure
    provides: ingest modules (grants_gov.py, sbir.py, usaspending.py) with working parse pipelines
provides:
  - grantflow/normalizers.py — shared normalization utilities for all ingest modules
  - Human-readable eligibility labels in opportunities.eligible_applicants (not raw codes)
  - Canonical agency names across all three sources
  - ISO 8601 dates in all date fields from all sources
  - Validated award_floor/ceiling pairs (invalid combos set to None)
affects:
  - 04-02 deduplication — canonical agency names and clean eligibility data are prerequisite
  - 05-search-api — eligibility filter API depends on human-readable labels, not raw codes
  - future phases consuming Opportunity.eligible_applicants or agency_name fields

# Tech tracking
tech-stack:
  added: []
  patterns:
    - normalize-at-ingest — all normalization happens at parse time before DB upsert, not post-hoc
    - shared-normalizers-module — pure stdlib module with no DB deps; all ingest modules import from it
    - strict-date-contract — unparseable dates return None rather than raw value (fail loudly)

key-files:
  created:
    - grantflow/normalizers.py
    - tests/test_normalizers.py
  modified:
    - grantflow/ingest/grants_gov.py
    - grantflow/ingest/sbir.py
    - grantflow/ingest/usaspending.py

key-decisions:
  - "normalize_date returns None (not raw value) for unparseable input — stricter than old _normalize_date in grants_gov.py; explicit parse failures are better than silently storing garbage"
  - "ELIGIBILITY_CODE_MAP and AGENCY_NAME_MAP are module-level constants in normalizers.py — no DB reads, cache-friendly, easy to extend"
  - "Unknown eligibility codes kept as-is (not dropped) — preserves data even for codes not in the map"
  - "Agency code slug for usaspending fixed: re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:50] replaces broken uppercase+space approach per CONCERNS.md"

patterns-established:
  - "Import pattern: from grantflow.normalizers import normalize_date, normalize_eligibility_codes, normalize_agency_name, validate_award_amounts"
  - "Normalizers applied immediately after field extraction, before record is appended to batch"

requirements-completed: [QUAL-01, QUAL-02, QUAL-05, QUAL-06]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 4 Plan 01: Data Quality Normalization Summary

**Shared normalizers module with CFDA code→label mapping, agency name canonicalization, ISO date enforcement, and award amount validation wired into all three ingest pipelines**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T18:38:10Z
- **Completed:** 2026-03-24T18:41:12Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created `grantflow/normalizers.py` — pure Python, no DB deps, exports four functions: `normalize_date`, `normalize_eligibility_codes`, `normalize_agency_name`, `validate_award_amounts`
- 50 unit tests covering all edge cases including strict None-on-garbage behavior for dates
- Removed local `_normalize_date` from grants_gov.py and `_parse_date` from sbir.py — single source of truth
- All three ingest modules now produce consistent, human-readable data before DB upsert

## Task Commits

Each task was committed atomically:

1. **Task 1: Create grantflow/normalizers.py with all normalization functions** - `79bd58f` (feat + test, TDD)
2. **Task 2: Wire normalizers into all three ingest modules** - `77e9107` (feat)

**Plan metadata:** (see final commit)

_Note: Task 1 used TDD — tests written first (RED), then implementation (GREEN). 50/50 pass._

## Files Created/Modified
- `grantflow/normalizers.py` — ELIGIBILITY_CODE_MAP (17 codes), AGENCY_NAME_MAP (30+ variants), normalize_date, validate_award_amounts, normalize_eligibility_codes, normalize_agency_name
- `tests/test_normalizers.py` — 50 unit tests across 4 test classes, all edge cases
- `grantflow/ingest/grants_gov.py` — removed _normalize_date, import normalizers, applied in both REST and XML parse paths
- `grantflow/ingest/sbir.py` — removed _parse_date, import normalizers, applied to awards and solicitations
- `grantflow/ingest/usaspending.py` — import normalizers, applied normalize_date to all date fields, normalize_agency_name to agency; fixed agency code slug bug

## Decisions Made
- `normalize_date` returns `None` for unparseable input (stricter than previous behavior) — fail loudly rather than store garbage strings
- Unknown eligibility codes are preserved as-is (not dropped) — better to store the raw code than lose data
- AGENCY_NAME_MAP covers 30+ variants across HHS, DOE, NSF, NIH, NASA, USDA, DOD, DOT, DOC, DOL, DOI, DOJ, VA, EPA, SBA
- USAspending agency code slug bug fixed inline (deviation Rule 1 — bug in CONCERNS.md)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed USAspending agency code slug generation**
- **Found during:** Task 2 (usaspending.py changes)
- **Issue:** CONCERNS.md flagged `agency_name.replace(" ", "_").upper()[:50]` as buggy — spaces only, leaves punctuation/special chars in code
- **Fix:** Replaced with `re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')[:50]` — proper slug, lowercase, strips leading/trailing underscores
- **Files modified:** grantflow/ingest/usaspending.py
- **Verification:** All 117 tests pass including existing usaspending-dependent tests
- **Committed in:** 77e9107 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix was explicitly called out in plan Task 2 spec. No scope creep.

## Issues Encountered
None — plan executed cleanly.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Normalization layer complete; Plan 04-02 (deduplication) can proceed
- All three ingest modules produce consistent agency names — deduplication cross-source matching is now reliable
- eligible_applicants field stores human-readable JSON arrays — API eligibility filter ready to use in Phase 5

---
*Phase: 04-data-quality*
*Completed: 2026-03-24*
