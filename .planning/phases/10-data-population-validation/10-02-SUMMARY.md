---
phase: 10-data-population-validation
plan: "02"
subsystem: ingest
tags: [sbir, sam_gov, csv, httpx, awards, opportunities]

# Dependency graph
requires:
  - phase: 10-01
    provides: normalizers wired into all four federal ingestors before new records created

provides:
  - SBIR awards table populated with 6,276 records (last 3 years)
  - SBIR ingestor fixed: _normalize_row() handles title-case CSV headers
  - SBIR ingestor fixed: seen_ids deduplication prevents intra-CSV UNIQUE constraint violations
  - SAM.gov ingestor confirmed to gracefully skip with status='skipped' when SAM_GOV_API_KEY absent

affects:
  - any phase querying awards or opportunities tables
  - SAM.gov ingestion (user must register at api.sam.gov for public-tier key)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_normalize_row() header normalization: convert title-case-with-spaces CSV headers to lowercase-underscore at read time so all downstream row.get() calls work without special-casing"
    - "seen_ids set for intra-CSV deduplication: track IDs added in current run to skip duplicate rows before they hit session.flush() UNIQUE constraint"

key-files:
  created: []
  modified:
    - grantflow/ingest/sbir.py

key-decisions:
  - "_normalize_row() normalizes headers at read time (not query time) — keeps all downstream row.get() calls clean and readable, O(1) per row"
  - "seen_ids set deduplicates intra-CSV duplicates — SBIR CSV contains rows with identical agency+company+date+title that hash to the same key; dedup before DB insert avoids UNIQUE constraint on batch flush"
  - "SAM.gov remains skipped (status='skipped') — SAM_GOV_API_KEY is a user_setup dependency; ingestor guard already correct, no code change needed"
  - "SBIR solicitations API returned 429 rate limit — retry logic handles gracefully, awards are primary data source, plan success not affected"

patterns-established:
  - "CSV field normalization: use _normalize_row() pattern for any ingestor reading CSVs with non-standard header formats"
  - "Intra-batch deduplication: use seen_ids set when source data may contain duplicate rows that would collide on keyed hash"

requirements-completed: [PIPE-03, PIPE-04]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 10 Plan 02: SBIR and SAM.gov Ingestion Summary

**Fixed SBIR ingestor (CSV field name mismatch + intra-CSV deduplication), ingested 6,276 SBIR awards; SAM.gov confirmed gracefully skipped pending user API key registration**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-24T22:48:44Z
- **Completed:** 2026-03-24T22:51:43Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Fixed root cause of SBIR crash: CSV headers are title-case-with-spaces (`'Award Year'`, `'Company'`, `'Proposal Award Date'`) but all `row.get()` calls expected lowercase-underscore keys — every row silently hit `continue` producing 0 records
- Added `_normalize_row()` to convert CSV headers at read time; all downstream field access now works correctly
- Fixed secondary bug: intra-CSV duplicate rows hash to same key; `seen_ids` set prevents UNIQUE constraint violations during `session.flush()`
- SBIR ingestion now completes with `status='success'`, 6,276 awards in database (last 3 years), no stuck entries
- Confirmed SAM.gov ingestor already has correct `status='skipped'` guard when `SAM_GOV_API_KEY` is absent — no code change needed

## Task Commits

1. **Task 1: Diagnose and fix SBIR ingestion** - `601315c` (fix)
2. **Task 2: Configure and run SAM.gov ingestion** - no code change (verification only)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/ingest/sbir.py` — Added `_normalize_row()` helper, `seen_ids` deduplication set, fixed `_make_award_key()` and record dict to use `company` key, updated `CSV_FIELD_MAP` comments

## Decisions Made

- `_normalize_row()` normalizes at read time (not query time): keeps all downstream `row.get()` calls clean, O(1) per row overhead
- `seen_ids` set chosen over `session.merge()`: simpler to reason about, explicit skip semantics, avoids SQLAlchemy merge semantics on Award model
- SAM.gov requires no code change: `status='skipped'` guard was already correct; this is a user_setup dependency documented below

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SBIR CSV field name mismatch (primary root cause)**
- **Found during:** Task 1 (diagnose SBIR crash)
- **Issue:** SBIR CSV uses title-case-with-spaces headers (`'Award Year'`, `'Company'`, `'Proposal Award Date'`) but `_ingest_awards()` used lowercase-underscore `row.get()` keys throughout. Every row hit the `continue` fallback — 0 records processed.
- **Fix:** Added `_normalize_row()` converting `k.lower().replace(" ", "_")` for all headers; updated `_make_award_key()` and record dict to use `company` key (CSV `'Company'` normalizes to `'company'`, not `'firm'`); updated `CSV_FIELD_MAP` comments.
- **Files modified:** `grantflow/ingest/sbir.py`
- **Verification:** Dry-run parsed 1,000 rows with correct field extraction; full run produced 6,276 records with `status='success'`
- **Committed in:** `601315c` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed intra-CSV duplicate row UNIQUE constraint violation**
- **Found during:** Task 1 (first post-fix run attempt)
- **Issue:** SBIR CSV contains rows with identical `agency+company+date+title` combinations that hash to the same `record_id`. `session.get(Award, record_id)` only checks the DB (not the in-session identity map for newly added but unflushed objects), so the second occurrence tried to `session.add()` a duplicate, causing `sqlite3.IntegrityError: UNIQUE constraint failed: awards.id` on `session.flush()`.
- **Fix:** Added `seen_ids: set[str]` tracking IDs added in the current run; skip rows whose `record_id` is already in `seen_ids`.
- **Files modified:** `grantflow/ingest/sbir.py`
- **Verification:** Ingestion completed without constraint errors; 6,276 unique awards inserted.
- **Committed in:** `601315c` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs)
**Impact on plan:** Both fixes were necessary for correctness. No scope creep.

## Issues Encountered

- SBIR solicitations API returned HTTP 429 on all 3 retry attempts — rate-limited. Retry logic handles this gracefully: awards (primary data) were already committed, solicitations logged as warning, `status='success'` unaffected.

## User Setup Required

SAM.gov ingestion requires a free API key:

1. Register at https://api.sam.gov (public-tier key, free)
2. Add to `.env`: `SAM_GOV_API_KEY=your_key_here`
3. Run: `uv run python -c "from grantflow.ingest.sam_gov import ingest_sam_gov; import json; print(json.dumps(ingest_sam_gov(), indent=2))"`

With a public-tier key (10 req/day), the first run will fetch up to 100 SAM.gov contract opportunities (10 pages × 10 records). Status will be `partial` if rate-limited or `success` if all pages fetched.

## Next Phase Readiness

- SBIR awards table has 6,276 records ready for query and enrichment
- SAM.gov ready to populate once user registers for API key
- No stuck `ingestion_log` entries; pipeline state is clean
- All 218 tests pass

---
*Phase: 10-data-population-validation*
*Completed: 2026-03-24*
