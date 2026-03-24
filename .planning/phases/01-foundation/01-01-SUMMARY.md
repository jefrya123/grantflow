---
phase: 01-foundation
plan: "01"
subsystem: database
tags: [postgresql, sqlite, sqlalchemy, alembic, asyncpg, psycopg2, migrations]

requires: []

provides:
  - Dual-dialect SQLAlchemy engine (PostgreSQL+psycopg2 or SQLite) selected at startup via GRANTFLOW_DATABASE_URL
  - Alembic migration tooling configured and pointing at grantflow.models.Base.metadata
  - Initial migration 0001 covering all four tables (opportunities, awards, agencies, ingestion_log)
  - asyncpg installed for future async engine upgrade

affects:
  - 01-02  # next plan in phase may build on migration tooling
  - All subsequent phases that run alembic upgrade head before schema changes

tech-stack:
  added: [asyncpg==0.31.0, psycopg2-binary==2.9.11, alembic==1.18.4, pytest-asyncio==1.3.0]
  patterns:
    - Dual-dialect engine: detect DATABASE_URL prefix at module load, branch on postgres vs sqlite
    - Alembic env.py injects URL at runtime — alembic.ini never stores credentials
    - psycopg2 for Alembic sync migrations, asyncpg available for future async ORM migration

key-files:
  created:
    - alembic.ini
    - alembic/env.py
    - alembic/versions/0001_initial_schema.py
  modified:
    - pyproject.toml
    - uv.lock
    - grantflow/database.py

key-decisions:
  - "Routes stay sync this phase — psycopg2 for sync engine, asyncpg reserved for future async migration"
  - "init_db() no longer creates SQLite FTS5 virtual table — removed SQLite-only artifact, PostgreSQL tsvector goes in Plan 02"
  - "Migration 0001 written manually (no live PostgreSQL in CI env) with explicit op.create_table() calls matching models.py exactly"
  - "alembic.ini sqlalchemy.url commented out — env.py injects real URL from GRANTFLOW_DATABASE_URL at runtime, no credential leakage"

patterns-established:
  - "Dialect detection: _is_postgres = DATABASE_URL.startswith('postgresql') or DATABASE_URL.startswith('postgres')"
  - "URL normalization: replace postgres:// with postgresql+psycopg2:// for SQLAlchemy sync engine"
  - "Alembic env.py pattern: import Base + DATABASE_URL, call config.set_main_option() before run_migrations_*"

requirements-completed: [FOUND-01, FOUND-03]

duration: 2min
completed: 2026-03-24
---

# Phase 1 Plan 01: PostgreSQL + Alembic Migration Foundation Summary

**Dual-dialect SQLAlchemy engine with psycopg2/asyncpg and Alembic 0001 migration covering all four tables (opportunities, awards, agencies, ingestion_log)**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-24T17:27:41Z
- **Completed:** 2026-03-24T17:29:29Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Installed asyncpg, psycopg2-binary, alembic, and pytest-asyncio via uv
- Reconfigured database.py to branch on PostgreSQL vs SQLite at import time; SQLite dev path retains all WAL pragmas unchanged
- Initialized Alembic directory with env.py wired to grantflow.models.Base and GRANTFLOW_DATABASE_URL
- Created initial migration 0001 with explicit op.create_table() + op.create_index() for all four models; downgrade() rolls back cleanly

## Task Commits

1. **Task 1: Install PostgreSQL dependencies and add Alembic** - `95c460d` (chore)
2. **Task 2: Reconfigure database.py and initialize Alembic** - `66e430a` (feat)

## Files Created/Modified

- `pyproject.toml` - Added asyncpg, psycopg2-binary, alembic in dependencies; pytest-asyncio in dev dependencies
- `uv.lock` - Locked all new dependencies
- `grantflow/database.py` - Replaced SQLite-only engine with dual-dialect pattern; removed FTS5 from init_db()
- `alembic.ini` - Alembic config; sqlalchemy.url commented out (injected by env.py at runtime)
- `alembic/env.py` - Imports DATABASE_URL + Base.metadata; normalizes postgres:// URL for psycopg2
- `alembic/versions/0001_initial_schema.py` - Initial migration: 4 tables, all indexes, clean downgrade

## Decisions Made

- Routes stay sync this phase — psycopg2 for the sync engine, asyncpg installed but reserved for a future async migration if needed
- FTS5 virtual table removed from init_db() — it was SQLite-only; PostgreSQL full-text search via tsvector goes in Plan 02
- Migration written manually with explicit DDL (no live PostgreSQL available in environment) to guarantee accuracy against models.py
- alembic.ini sqlalchemy.url left as a comment so credentials are never stored in version-controlled config files

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for this plan. To use PostgreSQL, set `GRANTFLOW_DATABASE_URL=postgresql://user:pass@host/dbname` and run `uv run alembic upgrade head`.

## Next Phase Readiness

- `alembic upgrade head` is now the authoritative way to create or update the schema against PostgreSQL
- SQLite local dev path (`uv run grantflow`) unchanged — zero regression
- Plan 02 can add PostgreSQL-specific columns (tsvector, JSONB) via new Alembic revisions
- asyncpg is installed and available if a future plan upgrades routes to async SQLAlchemy

---
*Phase: 01-foundation*
*Completed: 2026-03-24*
