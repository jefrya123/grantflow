---
phase: 04-data-quality
plan: "02"
subsystem: database
tags: [deduplication, canonical-id, sha256, alembic, sqlite, sqlalchemy]

requires:
  - phase: 04-01
    provides: normalized cfda_numbers, agency_code, close_date fields used as dedup fallback keys

provides:
  - grantflow/dedup.py with make_canonical_id, find_duplicate_groups, assign_canonical_ids
  - canonical_id column on opportunities table (migration 0005)
  - assign_canonical_ids wired into run_all.py ingest pipeline as step 9
  - 81856 existing records backfilled with canonical IDs (0 NULLs)

affects:
  - api-layer
  - search-results
  - any phase that queries opportunities table

tech-stack:
  added: []
  patterns:
    - "Raw SQL in assign_canonical_ids to avoid ORM full-column SELECT incompatibility between SQLAlchemy model (TSVECTORType) and SQLite schema"
    - "make_canonical_id is a pure function (no DB imports) — takes dict, returns deterministic hex string"
    - "Dedup pipeline step uses its own SessionLocal() instance, separate from ingester sessions"

key-files:
  created:
    - grantflow/dedup.py
    - alembic/versions/0005_add_canonical_id.py
    - tests/test_dedup.py
  modified:
    - grantflow/models.py
    - grantflow/ingest/run_all.py

key-decisions:
  - "Migration numbered 0005 (not 0003 as planned) — 0003 and 0004 were already claimed by pipeline_run_table and add_api_keys"
  - "assign_canonical_ids uses raw SQL SELECT (not ORM query) — SQLAlchemy ORM generates full-column SELECT including search_vector which does not exist in SQLite schema; raw SQL selects only required columns"
  - "make_canonical_id normalizes opportunity_number: strip whitespace, uppercase, collapse hyphens/spaces to single hyphen — ensures cross-source matches"
  - "Fallback key format: cfda|agency|close_date (pipe-separated, all lowercase) — used when opportunity_number is absent or empty"

patterns-established:
  - "Canonical ID format: canon_ + sha256(normalized_key)[:16] — 22 char total, collision-resistant for 80K+ records"
  - "Dedup step always runs at end of ingest pipeline, after CFDA linking (step 9)"
  - "find_duplicate_groups is read-only by contract — no commit/add calls"

requirements-completed:
  - QUAL-03

duration: 18min
completed: "2026-03-24"
---

# Phase 4 Plan 02: Cross-Source Deduplication Summary

**SHA-256 canonical IDs assigned to 81,856 opportunities via opportunity_number normalization with cfda+agency+date fallback, wired into ingest pipeline as step 9**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-24T18:45:00Z
- **Completed:** 2026-03-24T19:03:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `make_canonical_id`: deterministic sha256 hex ID — normalizes opportunity_number (strip, uppercase, collapse hyphens) with cfda+agency+date fallback
- `find_duplicate_groups`: read-only SQL GROUP BY query for cross-source duplicate detection
- `assign_canonical_ids`: batch NULL backfill via raw SQL (1000-row commits) — backfilled all 81,856 existing records
- Alembic migration 0005 applies `canonical_id TEXT` column + index cleanly
- `run_all.py` step 9 ensures every future ingest run assigns canonical IDs automatically
- 20 unit tests: all pass

## Task Commits

1. **Task 1: Create grantflow/dedup.py with canonical ID logic (TDD)** - `dcfee07` (feat)
2. **Task 2: Add migration 0005, wire into pipeline, backfill** - `55a3e24` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/dedup.py` - make_canonical_id, find_duplicate_groups, assign_canonical_ids
- `tests/test_dedup.py` - 20 unit tests covering normalization, fallback, determinism, read-only contract
- `alembic/versions/0005_add_canonical_id.py` - migration adding canonical_id TEXT + index
- `grantflow/models.py` - added canonical_id = Column(Text, nullable=True, index=True) to Opportunity
- `grantflow/ingest/run_all.py` - step 9: assign_canonical_ids called after CFDA linking

## Decisions Made

- Migration numbered 0005, not 0003 as written in plan — 0003/0004 already claimed
- `assign_canonical_ids` uses raw SQL `SELECT id, opportunity_number, cfda_numbers, agency_code, close_date FROM opportunities WHERE canonical_id IS NULL` instead of ORM query — SQLAlchemy's full-column ORM SELECT includes `search_vector` which does not exist in the SQLite schema (PostgreSQL-only column), causing `OperationalError`. Raw SQL selects only required columns and bypasses this incompatibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] assign_canonical_ids ORM query fails on SQLite due to TSVECTORType column**
- **Found during:** Task 2 (backfill step)
- **Issue:** SQLAlchemy ORM `session.query(Opportunity).filter(...)` generates `SELECT ... opportunities.search_vector ...` — this column exists in the model (TSVECTORType) but is not present in the SQLite schema. Results in `sqlite3.OperationalError: no such column: opportunities.search_vector`.
- **Fix:** Replaced ORM query with raw SQL using `session.execute(text("SELECT id, opportunity_number, cfda_numbers, agency_code, close_date FROM opportunities WHERE canonical_id IS NULL"))` — selects only the 5 columns needed for canonical ID generation
- **Files modified:** `grantflow/dedup.py`
- **Verification:** Backfill ran successfully: 81,856 assigned, 0 NULLs remain; all 20 dedup tests pass
- **Committed in:** `55a3e24` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required for correctness — ORM query was broken on the SQLite dev environment. Raw SQL fix is dialect-agnostic and will work on PostgreSQL too.

## Issues Encountered

- Migration number conflict: plan specified 0003 but that was already used by pipeline_run_table (noted in STATE.md from Phase 02). Used 0005 as next available revision, consistent with the decision pattern established in Phase 03.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- canonical_id is populated on all 81,856 opportunity records
- Same grant number across sources produces identical canonical_id — API consumers can deduplicate client-side
- `find_duplicate_groups` is available for a weekly dedup audit report
- Phase 5 (search/API) can expose canonical_id in response schema and use it for dedup filtering
- No blockers

---
*Phase: 04-data-quality*
*Completed: 2026-03-24*
