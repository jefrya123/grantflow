---
phase: 11-ada-compliance-grant-tagging-api
plan: "02"
subsystem: api
tags: [ada, endpoint, fastapi, tdd, pagination, municipality-filter]
dependency_graph:
  requires: [11-01]
  provides: [GET /api/v1/opportunities/ada-compliance]
  affects: [grantflow/api/routes.py]
tech_stack:
  added: []
  patterns: [fail-open municipality filter, nullslast sort, public endpoint without api key]
key_files:
  created:
    - tests/test_ada_compliance.py
    - grantflow/pipeline/ada_tagger.py
  modified:
    - grantflow/api/routes.py
key_decisions:
  - ada-compliance route registered before /{opportunity_id} — FastAPI path resolution requires static segments before path params (same pattern as export route)
  - No api_key dependency on get_ada_compliance_grants — public resource per CONTEXT.md locked decision
  - Municipality filter uses ilike on description + eligible_applicants with fail-open fallback — muni_query.count() > 0 check before narrowing
  - or_() import added to sqlalchemy imports in routes.py
  - ada_tagger.py copied from main branch (Plan 01 merge) since this worktree branched before Plan 01 merge
metrics:
  duration_minutes: 3
  completed_date: "2026-03-29"
  tasks_completed: 1
  files_changed: 3
---

# Phase 11 Plan 02: ADA Compliance API Endpoint Summary

**One-liner:** Public GET /api/v1/opportunities/ada-compliance endpoint with municipality filter, fail-open fallback, and deadline-proximity sort using SearchResponse schema.

## What Was Built

Added `GET /api/v1/opportunities/ada-compliance` to `grantflow/api/routes.py` as a public endpoint (no API key required). The route queries `Opportunity.topic_tags.ilike('%"ada-compliance"%')`, applies an optional municipality filter with fail-open behavior, sorts by `close_date ASC NULLS LAST`, and returns a paginated `SearchResponse`.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | ADA compliance endpoint with TDD | b95085c | grantflow/api/routes.py, tests/test_ada_compliance.py, grantflow/pipeline/ada_tagger.py |

## Test Results

- `uv run pytest tests/test_ada_compliance.py -x -v` — 31 passed (22 unit from Plan 01 + 9 integration)
- `uv run pytest tests/ -x` — 273 passed, 1 xpassed, 0 failed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Copied ada_tagger.py from main branch**
- **Found during:** Task 1 RED phase
- **Issue:** This worktree branched before the Plan 01 merge commit (e1b07fa). `grantflow/pipeline/ada_tagger.py` was not present, causing `from grantflow.pipeline.ada_tagger import ...` in the test file to fail.
- **Fix:** Copied `ada_tagger.py` from `main` branch via `git show main:grantflow/pipeline/ada_tagger.py` — identical content to what Plan 01 committed.
- **Files modified:** grantflow/pipeline/ada_tagger.py (created in worktree)
- **Commit:** b95085c

**2. [Rule 3 - Blocking] Package not installed in worktree venv**
- **Found during:** Task 1 RED phase
- **Issue:** Fresh worktree venv had no `grantflow` package installed; `ModuleNotFoundError` on conftest import.
- **Fix:** Ran `uv pip install -e .` to install editable package.

**3. [Observation] RED state was 401 not 404**
- The endpoint tests initially failed with 401 (not 404) because `ada-compliance` matched the `/{opportunity_id}` path param route which requires auth — confirming the route order problem was real. After adding the route, all tests pass with 200.

## Acceptance Criteria Check

- [x] `grantflow/api/routes.py` contains `def get_ada_compliance_grants(`
- [x] `grantflow/api/routes.py` contains `"/opportunities/ada-compliance"`
- [x] `grantflow/api/routes.py` contains `response_model=SearchResponse`
- [x] `grantflow/api/routes.py` contains `tags=["ada-compliance"]`
- [x] `grantflow/api/routes.py` contains `municipality: str | None = Query(`
- [x] `grantflow/api/routes.py` contains `ilike('%"ada-compliance"%')`
- [x] `grantflow/api/routes.py` contains `or_(` (municipality filter)
- [x] `grantflow/api/routes.py` contains `Opportunity.close_date.asc().nullslast()`
- [x] `grantflow/api/routes.py` does NOT contain `api_key` in `get_ada_compliance_grants` signature
- [x] `ada-compliance` appears in routes.py BEFORE `opportunity_id`
- [x] `tests/test_ada_compliance.py` contains `test_endpoint_returns_200`
- [x] `tests/test_ada_compliance.py` contains `test_municipality_filter`
- [x] `tests/test_ada_compliance.py` contains `test_municipality_fallback`
- [x] `tests/test_ada_compliance.py` contains `test_invalid_param_422`
- [x] `uv run pytest tests/test_ada_compliance.py -x` exits 0
- [x] `uv run pytest tests/ -x` exits 0

## Known Stubs

None — endpoint is fully wired to live database query.

## Self-Check: PASSED

- FOUND: grantflow/api/routes.py
- FOUND: tests/test_ada_compliance.py
- FOUND: grantflow/pipeline/ada_tagger.py
- FOUND: .planning/phases/11-ada-compliance-grant-tagging-api/11-02-SUMMARY.md
- FOUND: commit b95085c
