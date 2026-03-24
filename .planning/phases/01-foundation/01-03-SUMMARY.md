---
phase: 01-foundation
plan: "03"
subsystem: api, testing
tags: [fastapi, sqlalchemy, pytest, sqlite, tsvector, health-endpoint, ingestion-log]

requires:
  - phase: 01-01
    provides: PostgreSQL engine, Alembic migrations, IngestionLog model, Opportunity model

provides:
  - GET /api/v1/health endpoint returning pipeline freshness per source
  - tests/conftest.py with session-scoped SQLite engine and function-scoped db_session fixtures
  - tests/test_health.py with 5 tests covering empty DB, recent ingestion, stale detection, error logs, record counts
  - TSVECTORType TypeDecorator enabling SQLite test compatibility with PostgreSQL models

affects:
  - phase-02 (ingest pipeline will write IngestionLog rows surfaced here)
  - phase-03 (API consumers depend on /health for monitoring)

tech-stack:
  added: [pytest, fastapi.testclient, sqlalchemy TypeDecorator]
  patterns:
    - pytest fixtures with session-scoped engine and function-scoped rollback session
    - FastAPI dependency_overrides for test DB injection
    - TSVECTORType dialect-aware column type for cross-dialect test compatibility
    - select() for IN() subqueries (avoids SAWarning with Subquery coercion)

key-files:
  created:
    - tests/conftest.py
    - tests/test_health.py
    - .planning/phases/01-foundation/01-03-SUMMARY.md
  modified:
    - grantflow/api/routes.py
    - grantflow/models.py
    - pyproject.toml

key-decisions:
  - "TSVECTORType TypeDecorator renders TSVECTOR on PostgreSQL, TEXT on SQLite — enables test suite without mocking the model"
  - "pyproject.toml setuptools.packages.find include=[grantflow*] — required for editable install with multiple top-level dirs"
  - "select() used in IN() subquery — avoids SQLAlchemy SAWarning about coercing Subquery into select()"
  - "stale threshold is 48h on completed_at of status=success rows only — error logs do not trigger stale"

patterns-established:
  - "Test fixtures: scope=session engine + scope=function rollback session — tests are isolated, fast, no truncation needed"
  - "FastAPI test override: app.dependency_overrides[get_db] = override_get_db in client fixture"
  - "Health endpoint pattern: never 500, always return JSON even with empty DB"

requirements-completed: [FOUND-04]

duration: 12min
completed: "2026-03-24"
---

# Phase 1 Plan 03: Health Endpoint and First Test Coverage Summary

**GET /api/v1/health endpoint surfacing IngestionLog freshness per source, with pytest fixtures and 5 passing tests on SQLite**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-24T17:31:44Z
- **Completed:** 2026-03-24T17:43:56Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- GET /api/v1/health returns per-source last_ingestion_at, last_status, records_added_last_run, record_count, and stale flag
- overall_status is "stale" when any source's most recent success completed_at is older than 48 hours; "ok" otherwise (including empty DB)
- First test infrastructure for the project: conftest.py with session-scoped SQLite engine and per-test rollback sessions
- 5 tests covering empty DB, recent ingestion, stale detection, error log no-crash, and record count accuracy

## Task Commits

1. **Task 1: Add GET /api/v1/health endpoint** - `6195454` (feat)
2. **Task 2: Create test fixtures and health endpoint tests** - `cbbdee0` (test)

## Files Created/Modified

- `grantflow/api/routes.py` — Added /health endpoint, IngestionLog import, timezone import, select() fix for IN() subquery
- `grantflow/models.py` — Replaced bare TSVECTOR column with TSVECTORType TypeDecorator for SQLite compatibility
- `tests/conftest.py` — Session-scoped SQLite engine, function-scoped rollback session, TestClient fixture with dependency override
- `tests/test_health.py` — 5 test cases for health endpoint
- `pyproject.toml` — Added setuptools.packages.find to fix editable install with multiple top-level directories

## Decisions Made

- TSVECTORType TypeDecorator: renders as TSVECTOR on PostgreSQL dialect, TEXT on all others. Avoids mocking the model or conditionally excluding the column in tests.
- pyproject.toml package discovery fix: without `include = ["grantflow*"]`, setuptools refused editable install because of co-located `data/`, `static/`, `alembic/`, `templates/` directories.
- select() in IN() subquery: SQLAlchemy 2.x warns when a Subquery is coerced inside `.in_()` — using `select()` directly is the correct form.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed editable install failure due to multiple top-level packages**
- **Found during:** Task 2 (running tests)
- **Issue:** `uv pip install -e .` failed — setuptools discovered `data/`, `static/`, `alembic/`, `templates/` alongside `grantflow/` and refused to build
- **Fix:** Added `[tool.setuptools.packages.find]` with `include = ["grantflow*"]` to pyproject.toml
- **Files modified:** pyproject.toml
- **Verification:** `uv pip install -e .` succeeded
- **Committed in:** cbbdee0 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed TSVECTOR column incompatibility with SQLite test engine**
- **Found during:** Task 2 (first test run)
- **Issue:** `Base.metadata.create_all()` on SQLite raised `UnsupportedCompilationError` for TSVECTOR type — SQLite DDL compiler has no `visit_TSVECTOR` handler
- **Fix:** Introduced `TSVECTORType(TypeDecorator)` in models.py that dispatches to PostgreSQL TSVECTOR or Text based on dialect name
- **Files modified:** grantflow/models.py
- **Verification:** All 5 tests pass on SQLite; TSVECTOR column still used on PostgreSQL via load_dialect_impl
- **Committed in:** cbbdee0 (Task 2 commit)

**3. [Rule 1 - Bug] Fixed SQLAlchemy SAWarning for Subquery coercion in IN()**
- **Found during:** Task 2 (test run warnings)
- **Issue:** `.filter(IngestionLog.id.in_(subquery))` emitted SAWarning — SQLAlchemy 2.x requires an explicit `select()` statement in `.in_()`
- **Fix:** Changed subquery to use `select(func.max(...))` instead of `db.query(...).subquery()`
- **Files modified:** grantflow/api/routes.py
- **Verification:** Tests pass with 0 warnings
- **Committed in:** cbbdee0 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 bugs)
**Impact on plan:** All fixes required for correct test operation. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Health endpoint ready; will become meaningful once Phase 2 ingest pipeline writes IngestionLog rows
- Test infrastructure in place — future plans should add tests in tests/ following the conftest.py fixture pattern
- TSVECTORType pattern established — future models with PostgreSQL-specific column types should use the same TypeDecorator approach

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
