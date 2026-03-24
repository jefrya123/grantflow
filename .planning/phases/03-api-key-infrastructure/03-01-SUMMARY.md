---
phase: 03-api-key-infrastructure
plan: "01"
subsystem: api
tags: [api-keys, sha256, fastapi, sqlalchemy, alembic, security]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Base SQLAlchemy model, get_db dependency, TestClient conftest pattern
  - phase: 02-pipeline-hardening
    provides: Alembic migration chain (0003 pipeline_run_table is down_revision for 0004)

provides:
  - ApiKey SQLAlchemy model with key_hash, key_prefix, tier, is_active, created_at, last_used_at, request_count
  - Alembic migration 0004 creating api_keys table
  - POST /api/v1/keys endpoint returning plaintext key once, storing SHA-256 hash
  - Consistent error shape: {error_code, message} for all API errors
  - 9 passing tests in tests/test_api_keys.py

affects:
  - 03-02-rate-limiting (needs ApiKey model for lookup by hash)
  - 03-03-auth-middleware (needs key_hash lookup and is_active check)
  - all future API plans (must use {error_code, message} error shape)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "API key generation: gf_ + secrets.token_urlsafe(32), SHA-256 hash stored, plaintext returned once"
    - "Error shape: raise HTTPException(status_code=N, detail={error_code: str, message: str})"
    - "Alembic migration file naming: 0004_add_api_keys.py (incremental from existing head)"

key-files:
  created:
    - grantflow/api/keys.py
    - alembic/versions/0004_add_api_keys.py
    - tests/test_api_keys.py
  modified:
    - grantflow/models.py
    - grantflow/app.py

key-decisions:
  - "Migration uses revision 0004 not 0003 — 0003 was already claimed by pipeline_run_table migration"
  - "key_prefix = plaintext_key[:8] covers gf_ + 5 chars for display identification"
  - "Tier validation at endpoint layer (not DB constraint) — consistent error_code shape requires explicit 422 response"
  - "Body accepts optional dict (not Pydantic model) — Pydantic schemas added in Plan 03 of this phase"

patterns-established:
  - "Error shape: all API errors return {error_code: str, message: str} in HTTPException detail"
  - "Key issuance: SHA-256 hash only persisted, plaintext returned exactly once in creation response"

requirements-completed: [API-01, API-04]

# Metrics
duration: 12min
completed: 2026-03-24
---

# Phase 3 Plan 01: API Key Infrastructure Summary

**SHA-256-hashed API key issuance via POST /api/v1/keys with tier support, consistent {error_code, message} error shape, and Alembic migration 0004**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-24T18:20:00Z
- **Completed:** 2026-03-24T18:32:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- ApiKey SQLAlchemy model with 8 columns (id, key_hash, key_prefix, tier, is_active, created_at, last_used_at, request_count)
- Alembic migration 0004 with upgrade/downgrade (down_revision=0003)
- POST /api/v1/keys generates `gf_<token>`, stores SHA-256 hash, returns plaintext exactly once
- Consistent error shape `{error_code, message}` established for all API errors going forward
- 9 passing tests covering hash storage, prefix, tier validation, uniqueness, and error shape

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests** - `86dedcb` (test)
2. **Task 1 GREEN: ApiKey model and migration 0004** - `71fe047` (feat)
3. **Task 2 GREEN: POST /api/v1/keys endpoint** - `dae1bda` (feat)

_Note: TDD tasks have separate test→feat commits_

## Files Created/Modified

- `grantflow/models.py` - Added ApiKey model class
- `grantflow/api/keys.py` - POST /api/v1/keys endpoint with tier validation
- `grantflow/app.py` - Registered keys_router
- `alembic/versions/0004_add_api_keys.py` - Migration creating api_keys table with indexes
- `tests/test_api_keys.py` - 9 tests for endpoint behavior

## Decisions Made

- **Migration 0004 not 0003**: The plan specified revision ID 0003 but that was already taken by `pipeline_run_table`. Used 0004 to avoid collision — auto-fixed per Rule 1.
- **key_prefix = key[:8]**: Covers "gf_" + 5 chars, sufficient for display identification without leaking the secret portion.
- **Dict body not Pydantic**: Body accepts `dict | None` for simplicity; Pydantic response schemas are added in Plan 03 of this phase.
- **Tier validation at endpoint**: Explicit 422 with `{error_code, message}` shape rather than relying on Pydantic enum validation, which would return a different error format.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migration revision ID changed from 0003 to 0004**
- **Found during:** Task 1 (migration creation)
- **Issue:** Plan specified revision ID `0003` but `alembic/versions/0003_pipeline_run_table.py` already uses that ID
- **Fix:** Created migration as `0004_add_api_keys.py` with `revision='0004'` and `down_revision='0003'`
- **Files modified:** alembic/versions/0004_add_api_keys.py
- **Verification:** `ls alembic/versions/ | grep 0004` confirms file; Alembic chain is valid
- **Committed in:** 71fe047 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - collision avoidance)
**Impact on plan:** Necessary correction, no scope change. Migration chain is correct and complete.

## Issues Encountered

None beyond the migration ID collision above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ApiKey model and endpoint ready for Plan 02 (rate limiting) and Plan 03 (auth middleware)
- `grantflow/api/keys.py` exports `router` — ready for auth middleware integration
- Migration 0004 ready to apply (`alembic upgrade head` in Plan 02)
- Error shape `{error_code, message}` established — all future API error handlers must use this pattern

---
*Phase: 03-api-key-infrastructure*
*Completed: 2026-03-24*
