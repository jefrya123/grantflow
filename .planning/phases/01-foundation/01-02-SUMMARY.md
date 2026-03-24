---
phase: 01-foundation
plan: "02"
subsystem: database
tags: [postgresql, tsvector, fts, gin-index, alembic, sqlalchemy]

requires:
  - phase: 01-foundation plan 01
    provides: Initial schema, Alembic 0001 migration, Opportunity model, API/web routes

provides:
  - search_vector tsvector column on Opportunity model (PostgreSQL GIN-indexed)
  - Alembic migration 0002 with GIN index, trigger function, and backfill UPDATE
  - PostgreSQL to_tsquery() FTS path in api/routes.py and web/routes.py
  - SQLite LIKE fallback for dev/local environments

affects: [02-ingest, 03-api, any phase touching FTS or search queries]

tech-stack:
  added: [sqlalchemy.dialects.postgresql.TSVECTOR]
  patterns:
    - "Dialect-aware FTS: check DATABASE_URL prefix to branch between tsvector and LIKE"
    - "PostgreSQL trigger auto-populates search_vector on INSERT/UPDATE"
    - "Alembic raw SQL DDL for PostgreSQL-specific objects (trigger, GIN index)"

key-files:
  created:
    - alembic/versions/0002_add_tsvector_fts.py
  modified:
    - grantflow/models.py
    - grantflow/api/routes.py
    - grantflow/web/routes.py

key-decisions:
  - "TSVECTOR imported at module level from sqlalchemy.dialects.postgresql (always importable, no try/except needed)"
  - "FTS dialect detection via DATABASE_URL string prefix check (_DB_URL.startswith('postgresql')) — simple and zero-overhead"
  - "Ingest-layer FTS5 references in grants_gov.py and run_all.py deferred to Phase 2 ingest migration (out of scope for this plan)"

patterns-established:
  - "Dialect branch pattern: if _DB_URL.startswith('postgresql') use tsvector, else LIKE fallback"
  - "Module-level imports only in route files — no deferred imports inside route functions"

requirements-completed: [FOUND-02]

duration: 15min
completed: 2026-03-24
---

# Phase 1 Plan 02: PostgreSQL tsvector Full-Text Search Summary

**PostgreSQL tsvector column with GIN index and auto-update trigger replacing SQLite FTS5 virtual table, with LIKE fallback preserved for dev**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-24T17:35:00Z
- **Completed:** 2026-03-24T17:50:00Z
- **Tasks:** 2
- **Files modified:** 4 (models.py, api/routes.py, web/routes.py, + 1 created)

## Accomplishments

- Added `search_vector` tsvector column to `Opportunity` model using SQLAlchemy's postgresql dialect
- Created Alembic migration 0002 with GIN index, trigger function (auto-populates on INSERT/UPDATE), and backfill UPDATE for existing rows
- Replaced FTS5 `opportunities_fts MATCH` query in both API and web routes with `search_vector @@ to_tsquery('english', q)`
- Added SQLite LIKE fallback (title/description/agency_name) for dev environments where DATABASE_URL is not postgresql://
- Moved deferred imports (`from fastapi import HTTPException`, `from sqlalchemy import text`) to module level in web/routes.py

## Task Commits

1. **Task 1: Add search_vector column to models.py and create Alembic migration 0002** - `abf8fa6` (feat)
2. **Task 2: Update FTS query in API and web routes to use tsvector** - `401ae30` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `grantflow/models.py` - Added `search_vector = Column(TSVECTOR, nullable=True)` to Opportunity
- `alembic/versions/0002_add_tsvector_fts.py` - Migration: tsvector column, GIN index, trigger function, backfill UPDATE
- `grantflow/api/routes.py` - FTS5 block replaced with to_tsquery/LIKE branch; `text` import removed; DATABASE_URL imported
- `grantflow/web/routes.py` - Same FTS replacement; deferred imports moved to module level; `func` added to top-level imports

## Decisions Made

- TSVECTOR imported at module level (not conditionally) — SQLAlchemy's postgresql dialect is always available regardless of DB connection
- Dialect detection uses `DATABASE_URL.startswith("postgresql")` — covers both `postgresql://` and `postgres://` URI schemes
- Ingest files (`grants_gov.py`, `run_all.py`) still reference FTS5 virtual table — these are deferred to Phase 2 ingest work, logged in `deferred-items.md`

## Deviations from Plan

None - plan executed exactly as written. The ingest-layer FTS5 references found during verification are pre-existing out-of-scope code, logged as deferred items rather than auto-fixed.

## Issues Encountered

- A linter auto-modified `api/routes.py` between the initial read and first edit (added `IngestionLog` import, `timezone` to datetime imports, added `/health` endpoint). Re-read the file before editing to capture the current state. No functional impact.

## User Setup Required

None - no external service configuration required. The migration runs via `uv run alembic upgrade head` against a PostgreSQL instance. SQLite dev path continues to work without migration.

## Next Phase Readiness

- tsvector FTS infrastructure is in place; Phase 2 ingest pipeline can rely on the trigger to auto-populate `search_vector` on INSERT
- Ingest files (`grants_gov.py`, `run_all.py`) still contain FTS5 virtual table rebuild code — must be removed in Phase 2 ingest plan to avoid errors on PostgreSQL
- `alembic upgrade head` must be run against the production PostgreSQL instance before deploying search changes

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
