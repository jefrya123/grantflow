---
phase: 06-advanced-api-web-ui
plan: 01
subsystem: api
tags: [export, csv, streaming, schema, agencies, query-builder, tdd]
dependency_graph:
  requires: []
  provides: [bulk-export-endpoint, agency-response-schema, shared-query-builder]
  affects: [grantflow/api/routes.py, grantflow/api/schemas.py, grantflow/api/query.py]
tech_stack:
  added: [StreamingResponse, csv.writer, JSONResponse]
  patterns: [shared-query-builder, tdd-red-green, streaming-csv-export]
key_files:
  created:
    - grantflow/api/query.py
    - tests/test_export.py
    - tests/test_agencies.py
  modified:
    - grantflow/api/routes.py
    - grantflow/api/schemas.py
    - tests/test_schemas.py
decisions:
  - "Export route registered before /{opportunity_id} — FastAPI path resolution requires static segments before path params"
  - "StreamingResponse with csv.writer generator for CSV export — avoids buffering 10k rows in memory"
  - "source='export_test' in test fixtures — prevents test data leaking into health endpoint's grants_gov count"
  - "Hard cap at 10,000 via .limit(10_000) on query builder result — applied before serialization"
  - "AgencyResponse has Optional code and name — some DB rows have NULL agency_code"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-24"
  tasks_completed: 2
  files_created: 3
  files_modified: 3
---

# Phase 06 Plan 01: API Completion (Export + Agencies Schema) Summary

**One-liner:** Bulk export endpoint (CSV/JSON via StreamingResponse), shared query builder extracted from duplicated filter logic, AgencyResponse schema locking agencies contract, and linked-awards integration test verifying API-06.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extract shared query builder + bulk export endpoint | c605058 | grantflow/api/query.py, grantflow/api/routes.py, tests/test_export.py |
| 2 | AgencyResponse schema + linked awards test coverage | 67ee7ea | grantflow/api/schemas.py, grantflow/api/routes.py, tests/test_agencies.py, tests/test_schemas.py |

## What Was Built

### Task 1: Shared Query Builder + Bulk Export

`grantflow/api/query.py` — new module with `build_opportunity_query()` that centralizes all filter logic (FTS + 9 filter params). Eliminates duplication between `/search` and `/export`.

`/api/v1/opportunities/export` — new endpoint registered BEFORE `/{opportunity_id}` to avoid FastAPI path ambiguity:
- `format=csv` → `StreamingResponse` with `csv.writer` generator, `Content-Disposition: attachment; filename=opportunities.csv`
- `format=json` → `JSONResponse` with `{"results": [...], "total": N}`
- Rate limited to `100/day` (stricter than search)
- Hard-capped at 10,000 rows via `.limit(10_000)`
- Requires API key (401 without)
- Passes all filter params to `build_opportunity_query()`

### Task 2: AgencyResponse Schema + Awards Coverage

`AgencyResponse` Pydantic model added to `schemas.py`:
```python
class AgencyResponse(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    opportunity_count: int
```

`get_agencies()` in `routes.py` now has `response_model=list[AgencyResponse]` — field contract is locked.

`test_opportunity_detail_awards` in `tests/test_schemas.py` — creates an Opportunity + Award linked by `opportunity_number`, verifies `GET /opportunities/{id}` returns non-empty `awards` list with `AwardResponse` fields (API-06 verified).

## Verification

```
tests/test_export.py:    6 passed
tests/test_agencies.py:  14 passed
tests/test_schemas.py:   8 passed (including new linked-awards test)
Full suite:              170 passed, 1 xpassed, 0 failed
```

Route ordering confirmed: `/opportunities/export` at index 6, `/{opportunity_id}` at index 7.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test data leaking into health endpoint count**
- **Found during:** Task 1, full-suite regression run
- **Issue:** `test_export_*` fixtures used `source='grants_gov'`, which persisted in the session-scoped SQLite test engine and inflated the record count seen by `test_health_record_counts` (expected 3, got 12)
- **Fix:** Changed `make_opportunity()` default `source` to `'export_test'` — distinct from any real source name
- **Files modified:** tests/test_export.py
- **Commit:** c605058

## Self-Check: PASSED

- FOUND: grantflow/api/query.py
- FOUND: tests/test_export.py
- FOUND: tests/test_agencies.py
- FOUND: commit c605058 (query builder + export)
- FOUND: commit 67ee7ea (AgencyResponse schema)
- FOUND: commit f1e9fba (agencies tests)
- FOUND: commit 716bc47 (linked-awards test)
- FOUND: commit 99582fd (export tests RED)
