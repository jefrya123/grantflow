---
phase: 09-api-feature-polish
plan: "01"
subsystem: api
tags: [rate-limiting, export, tier-limits, slowapi]
dependency_graph:
  requires: []
  provides: [tier-aware-rate-limits, export-topic-filter]
  affects: [grantflow/api/auth.py, grantflow/api/routes.py]
tech_stack:
  added: []
  patterns: [_session_factory monkeypatch pattern for testable sync DB callables]
key_files:
  created: [tests/test_auth_ratelimit.py (extended), tests/test_export.py (extended)]
  modified:
    - grantflow/api/auth.py
    - grantflow/api/routes.py
decisions:
  - "_session_factory module-level var in auth.py: allows tests to monkeypatch the session factory used by _tier_limit/_tier_export_limit without touching the callable signature"
  - "TIER_LIMITS['free'] // 10 = 100 export limit: preserves original 10:1 ratio (100/day free, 1000/day starter, 10000/day growth)"
metrics:
  duration: 2min
  completed: "2026-03-24"
  tasks: 2
  files: 4
---

# Phase 09 Plan 01: Tier-Aware Rate Limits and Export Topic Filter Summary

**One-liner:** Wired slowapi tier-aware dynamic rate limits (free=1000, starter=10000, growth=100000/day) and fixed export endpoint silently dropping the ?topic= filter since Phase 7.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Tier-aware rate limit callables and endpoint wiring | c176ea7 |
| 2 | Export topic filter and topic_tags CSV column | 48548f2 |

## What Was Built

### Task 1: Tier-aware rate limit callables

Added `_tier_limit(key: str) -> str` and `_tier_export_limit(key: str) -> str` to `grantflow/api/auth.py`. Both callables:
- Hash the raw API key with SHA-256
- Open a fresh DB session via `_session_factory` (module-level variable)
- Look up `ApiKey.tier` by `key_hash` + `is_active`
- Return the appropriate limit string (default: free tier if key not found)

All four data endpoints (`search_opportunities`, `get_opportunity`, `get_stats`, `get_agencies`) now use `@limiter.limit(_tier_limit)`. The export endpoint uses `@limiter.limit(_tier_export_limit)`.

### Task 2: Export topic filter and CSV column

- Added `topic: str | None = Query(default=None)` parameter to `export_opportunities()`
- Passes `topic=topic` to `build_opportunity_query()` (which already supported it since Phase 7)
- Added `"topic_tags"` to `_EXPORT_CSV_COLUMNS` list

## Tests Added

**tests/test_auth_ratelimit.py** (6 new tests):
- `test_tier_limit_free` — free key returns "1000/day"
- `test_tier_limit_starter` — starter key returns "10000/day"
- `test_tier_limit_growth` — growth key returns "100000/day"
- `test_tier_limit_unknown_key` — unknown key returns "1000/day" (free default)
- `test_tier_export_limit_free` — free key returns "100/day"
- `test_tier_export_limit_growth` — growth key returns "10000/day"

**tests/test_export.py** (3 new tests):
- `test_export_topic_filter` — health topic returns health-tagged rows
- `test_export_topic_filter_excludes` — health topic excludes education-only rows
- `test_export_csv_includes_topic_tags` — CSV header includes "topic_tags"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing testability] Added `_session_factory` module-level variable**
- **Found during:** Task 1 GREEN phase — `_tier_limit` opened a `SessionLocal()` that connected to `grantflow.db`, not the test SQLite DB
- **Issue:** Tests inserted rows into `test_grantflow.db` but the callable queried the production DB path, causing tier lookups to always return free default
- **Fix:** Introduced `_session_factory = SessionLocal` module-level var in `auth.py`; tests use `monkeypatch` via `patched_session_factory` fixture to redirect to test session
- **Files modified:** `grantflow/api/auth.py`, `tests/test_auth_ratelimit.py`
- **Commit:** c176ea7

## Self-Check

### Files Created/Modified

- `/home/jeff/Projects/grantflow/grantflow/api/auth.py` — _tier_limit, _tier_export_limit, _session_factory
- `/home/jeff/Projects/grantflow/grantflow/api/routes.py` — 4x _tier_limit, 1x _tier_export_limit, topic param on export
- `/home/jeff/Projects/grantflow/tests/test_auth_ratelimit.py` — 6 new tier tests
- `/home/jeff/Projects/grantflow/tests/test_export.py` — 3 new topic filter tests

### Commits
- c176ea7: feat(09-01): tier-aware rate limit callables and endpoint wiring
- 48548f2: feat(09-01): export topic filter and topic_tags CSV column

### Test Results
- `uv run pytest tests/test_auth_ratelimit.py tests/test_export.py`: 25 passed
- `uv run pytest tests/`: 199 passed, 1 xpassed

## Self-Check: PASSED
