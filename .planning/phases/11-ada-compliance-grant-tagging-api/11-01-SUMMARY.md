---
phase: 11-ada-compliance-grant-tagging-api
plan: "01"
subsystem: pipeline
tags: [ada, accessibility, keyword-matching, backfill, sqlite, raw-sql, tdd]

# Dependency graph
requires:
  - phase: 07-gtm-enrichment
    provides: topic_tags TEXT column (JSON string) on opportunities table
  - phase: 10-data-population-validation
    provides: raw SQL SELECT pattern (avoids ORM search_vector issue)
provides:
  - ADA keyword matching function (_is_ada_match) with false-positive prevention
  - Backfill CLI script (run_ada_backfill) that tags matching rows idempotently
  - 22 unit tests covering keyword accuracy and backfill correctness
affects:
  - 11-ada-compliance-grant-tagging-api (Plans 02+: API filter, search UI badge)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Raw SQL SELECT + UPDATE pattern (not ORM) to avoid search_vector column issue in SQLite"
    - "Contextually qualified keyword lists (no bare 'ada') for false positive prevention"
    - "Idempotent backfill: parse existing tags, append only if absent, single commit at end"
    - "TDD: RED commit with failing ImportError, GREEN commit with 22/22 passing"

key-files:
  created:
    - grantflow/pipeline/ada_tagger.py
    - tests/test_ada_compliance.py
  modified: []

key-decisions:
  - "No bare 'ada' in keyword lists — all entries are contextually qualified to prevent false positives on 'adaptation', 'Adams', 'academic', 'NADAC'"
  - "ADA_AGENCY_KEYWORDS contains only 'federal transit administration' — Office of Special Education excluded per RESEARCH.md to avoid tagging IDEA/education grants"
  - "run_ada_backfill uses raw SQL SELECT (not ORM) — consistent with existing pattern from Phase 10 that avoids search_vector column missing in SQLite"
  - "Single commit at end of backfill loop — not per-row — for performance and atomicity"

patterns-established:
  - "ADA tagger: _is_ada_match / _parse_tags / run_ada_backfill as stable public API for Phase 11 Plans 02+"
  - "Backfill CLI pattern: if __name__ == '__main__' calls function and prints count; callable as uv run python -m grantflow.pipeline.ada_tagger"

requirements-completed: [ADA-01]

# Metrics
duration: 15min
completed: 2026-03-29
---

# Phase 11 Plan 01: ADA Tagger Summary

**ADA keyword matcher + idempotent backfill CLI using contextually qualified 3-list keyword matching against topic_tags JSON column, 22/22 unit tests passing**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-29T00:13:00Z
- **Completed:** 2026-03-29T00:28:36Z
- **Tasks:** 1 (TDD: 2 commits — test + implementation)
- **Files modified:** 2

## Accomplishments

- `_is_ada_match(title, description, agency_name)` with three contextually qualified keyword lists — no bare "ada" entry prevents false positives on "adaptation", "Adams", "academic", "NADAC"
- `run_ada_backfill(db=None)` uses raw SQL SELECT + UPDATE (not ORM), is idempotent, handles malformed JSON gracefully, single-commit for atomicity
- 22 unit tests covering 8 true-positive cases, 6 false-positive prevention cases, 4 tag-parsing cases, and 4 backfill integration cases (tagging, idempotency, tag preservation, malformed recovery)
- CLI callable via `uv run python -m grantflow.pipeline.ada_tagger`

## Task Commits

TDD task with two commits:

1. **RED — test(11-01):** add failing tests for ADA keyword matching and backfill — `143146b`
2. **GREEN — feat(11-01):** implement ADA keyword matcher and backfill CLI script — `c1d1a54`

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/pipeline/ada_tagger.py` — ADA_TITLE_KEYWORDS, ADA_DESC_KEYWORDS, ADA_AGENCY_KEYWORDS, _is_ada_match, _parse_tags, run_ada_backfill, __main__ block
- `tests/test_ada_compliance.py` — 22 unit tests across TestKeywordMatchingTrue, TestKeywordMatchingFalse, TestParseTags, TestBackfill

## Decisions Made

- No bare `"ada"` as a standalone keyword — all 24 title keywords, 13 description keywords, and 1 agency keyword are contextually qualified phrases
- `ADA_AGENCY_KEYWORDS` contains only `"federal transit administration"` — `"office of special education"` excluded per RESEARCH.md recommendation
- Raw SQL pattern (not ORM) to avoid `search_vector` column absent in SQLite — consistent with Phase 10 established pattern
- `run_ada_backfill` does a single `db.commit()` after the full loop, not per-row, for performance and atomicity

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `grantflow` package not installed in editable mode in the fresh worktree `.venv` — resolved via `uv pip install -e .` before running tests. Not a code issue; worktree environment initialization.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `run_ada_backfill`, `_is_ada_match`, and `_parse_tags` are stable public exports for Plan 02 (API filter endpoint) and Plan 03 (search UI badge)
- Run `uv run python -m grantflow.pipeline.ada_tagger` against production DB to populate `ada-compliance` tags before deploying API filter

---
*Phase: 11-ada-compliance-grant-tagging-api*
*Completed: 2026-03-29*
