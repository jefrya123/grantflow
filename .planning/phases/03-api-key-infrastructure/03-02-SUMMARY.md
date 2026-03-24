---
phase: 03-api-key-infrastructure
plan: "02"
subsystem: api
tags: [auth, rate-limiting, slowapi, fastapi, sha256, api-keys]

# Dependency graph
requires:
  - phase: 03-api-key-infrastructure
    plan: "01"
    provides: ApiKey model, key_hash lookup, error shape {error_code, message}

provides:
  - get_api_key() FastAPI dependency validating X-API-Key header via SHA-256 lookup
  - TIER_LIMITS dict mapping tiers to daily limits (free=1000, starter=10000, growth=100000)
  - slowapi Limiter wired to app; 1000/day rate limit on all protected endpoints
  - Custom 429 handler returning {error_code: RATE_LIMIT_EXCEEDED} with Retry-After header
  - All data endpoints (search, get_opportunity, stats, agencies) protected with Depends(get_api_key)
  - /health and /docs remain public
  - 10 passing tests in tests/test_auth_ratelimit.py

affects:
  - all future API consumers (must pass X-API-Key header)
  - Phase 6 rate limiting (TIER_LIMITS in auth.py is the extension point)

# Tech tracking
tech-stack:
  added:
    - "slowapi==0.1.9 — ASGI rate limiting middleware for FastAPI"
    - "limits==5.8.0 — rate limit storage/counting backend (slowapi dependency)"
  patterns:
    - "get_api_key(): async FastAPI dependency; SHA-256 hash lookup, updates last_used_at + request_count"
    - "Limiter key_func: X-API-Key header with get_remote_address fallback for public endpoints"
    - "Custom rate-limit handler: JSONResponse with {detail: {error_code, message}} + Retry-After header"
    - "TDD: RED (failing tests) → GREEN (implementation) per task, committed separately"

key-files:
  created:
    - grantflow/api/auth.py
    - tests/test_auth_ratelimit.py
  modified:
    - grantflow/app.py
    - grantflow/api/routes.py
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Limiter imported from app.py into routes.py to share single Limiter instance — avoids dual-limiter state"
  - "Alembic stamped at 0004 (not upgraded) — api_keys table pre-existed from Plan 01 Base.metadata.create_all()"
  - "1000/day limit on all protected endpoints regardless of tier — Phase 6 will implement per-tier dynamic limiting"
  - "get_api_key is async — consistent with FastAPI async dependency conventions; asyncio.run() used in unit tests"

requirements-completed: [API-02, API-04]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 3 Plan 02: X-API-Key Auth and Rate Limiting Summary

**get_api_key() FastAPI dependency with SHA-256 lookup, slowapi 1000/day rate limiting on all data endpoints, /health and /docs public**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-24T18:30:38Z
- **Completed:** 2026-03-24T18:33:13Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- `grantflow/api/auth.py` — `get_api_key()` dependency: validates X-API-Key header, SHA-256 lookup, 401 on missing/invalid key, updates `last_used_at` and `request_count` on each valid call
- `TIER_LIMITS` dict exported from auth.py: free=1000, starter=10000, growth=100000
- `slowapi` Limiter configured in `app.py` with X-API-Key key_func and IP fallback
- `SlowAPIMiddleware` wired; custom 429 handler returns `{error_code: RATE_LIMIT_EXCEEDED, message}` with `Retry-After` header
- All 4 data endpoints (search, get_opportunity, stats, agencies) protected with `Depends(get_api_key)` and `@limiter.limit("1000/day")`
- `/health` and `/docs` remain public — no auth dependency
- Alembic chain at 0004 (head) — stamped since table pre-existed from Plan 01
- 10 new tests; 67 total tests passing with no regressions

## Task Commits

1. **Task 1 RED: Failing auth dependency tests** — `4e8a20b` (test)
2. **Task 1 GREEN: get_api_key() + TIER_LIMITS + slowapi install** — `1b4985f` (feat)
3. **Task 2 RED: Failing integration tests for wired endpoints** — `547d099` (test)
4. **Task 2 GREEN: Wire auth+rate limiting to routes, app middleware** — `127cd41` (feat)

## Files Created/Modified

- `grantflow/api/auth.py` — get_api_key() dependency, TIER_LIMITS
- `grantflow/app.py` — Limiter, SlowAPIMiddleware, custom_rate_limit_handler
- `grantflow/api/routes.py` — Depends(get_api_key) + @limiter.limit on search, get_opportunity, stats, agencies
- `tests/test_auth_ratelimit.py` — 10 tests (4 unit, 6 integration)
- `pyproject.toml` + `uv.lock` — slowapi>=0.1.9 added

## Decisions Made

- **Shared Limiter via import**: `routes.py` imports `limiter` from `grantflow.app` to ensure single in-memory counter state. A second `Limiter()` instance would create split counters.
- **Alembic stamp not upgrade**: The `api_keys` table was already created by `Base.metadata.create_all()` in Plan 01's `init_db()`. Running `alembic upgrade head` would fail with "table already exists". `alembic stamp head` records the migration as applied without executing DDL.
- **Flat 1000/day limit**: slowapi does not natively support per-key dynamic limits in decorators. All protected endpoints use `1000/day` (free tier floor). Per-tier enforcement is deferred to Phase 6 with a custom rate limit backend.
- **async get_api_key**: FastAPI dependency injection works with both sync and async functions. Async chosen for consistency with FastAPI conventions; unit tests use `asyncio.run()` to call it directly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Alembic stamp instead of upgrade**
- **Found during:** Task 2 (alembic upgrade head)
- **Issue:** `api_keys` table was already created by `Base.metadata.create_all()` in Plan 01's lifespan handler — `alembic upgrade head` raised `sqlite3.OperationalError: table api_keys already exists`
- **Fix:** Ran `alembic stamp head` to advance migration tracking to 0004 without executing DDL
- **Files modified:** None (Alembic version tracking in DB only)
- **Verification:** `uv run alembic current` returns `0004 (head)`
- **Committed in:** 127cd41 (Task 2 commit message notes this)

---

**Total deviations:** 1 auto-fixed (Rule 1 — Alembic state collision)
**Impact on plan:** No scope change. Migration chain is correct at 0004 (head). The root cause (init_db vs alembic conflict) is a pre-existing pattern established in Phase 1.

## Issues Encountered

None beyond the Alembic stamp issue above.

## User Setup Required

None — all changes are internal. API consumers must now include `X-API-Key: <key>` header on data endpoint requests.

## Next Phase Readiness

- Auth gate is live — all monetizable endpoints now require a valid API key
- `TIER_LIMITS` in `grantflow/api/auth.py` is the extension point for Phase 6 per-tier limiting
- `get_api_key()` returns the full `ApiKey` row — tier, request_count, last_used_at all accessible for usage analytics
- Rate limiting infrastructure ready — custom handler + Retry-After header fully implemented

---
*Phase: 03-api-key-infrastructure*
*Completed: 2026-03-24*
